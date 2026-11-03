// Build with GCC and -O3 -std=c++17 -fopenmp. Input is little-endian.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <omp.h>

struct Trip {
    double lat1, lon1, lat2, lon2, miles;
    std::int32_t hour, seconds;
};
static_assert(sizeof(Trip) == 48);
struct Bucket {
    std::int64_t trips{}, metered{}, direct{}, seconds{};
    Bucket& operator+=(const Bucket& x) {
        trips += x.trips; metered += x.metered; direct += x.direct; seconds += x.seconds;
        return *this;
    }
};
using Table = std::array<Bucket, 24>;
#pragma omp declare reduction(add_bucket : Bucket : omp_out += omp_in) initializer(omp_priv = Bucket{})

inline Bucket measure(const Trip& t) {
    constexpr double rad = 0.017453292519943295;
    double a = std::sin((t.lat2 - t.lat1) * rad / 2);
    double b = std::sin((t.lon2 - t.lon1) * rad / 2);
    double h = a*a + std::cos(t.lat1*rad) * std::cos(t.lat2*rad) * b*b;
    double direct = 12742000.0 * std::asin(std::sqrt(std::clamp(h, 0.0, 1.0)));
    return {1, std::llround(t.miles * 1609.344), std::llround(direct), t.seconds};
}

void sequential(const std::vector<Trip>& trips, Table& out) {
    for (const Trip& t : trips) out[t.hour] += measure(t);
}
void parallel(const std::vector<Trip>& trips, Bucket* out) {
    #pragma omp parallel for schedule(runtime) reduction(add_bucket:out[:24])
    for (std::int64_t i = 0; i < static_cast<std::int64_t>(trips.size()); ++i)
        out[trips[i].hour] += measure(trips[i]);
}
std::int64_t scan_stride(const std::vector<Trip>& trips, int stride) {
    std::int64_t sum = 0;
    for (int offset = 0; offset < stride; ++offset)
        for (size_t i = offset; i < trips.size(); i += stride) sum += trips[i].seconds;
    return sum;
}
using Clock = std::chrono::steady_clock;
double elapsed(Clock::time_point from) {
    return std::chrono::duration<double>(Clock::now()-from).count();
}

int main(int argc, char** argv) try {
    if (argc != 6) throw std::runtime_error("usage: taxi FILE serial|omp|stride THREADS static|dynamic|guided|STRIDE REPEATS");
    std::string mode = argv[2], policy = argv[4];
    int threads = std::stoi(argv[3]), repeats = std::stoi(argv[5]);
    if (threads < 1 || repeats < 1) throw std::runtime_error("positive threads and repeats required");
    auto before_load = Clock::now();
    std::ifstream in(argv[1], std::ios::binary | std::ios::ate);
    if (!in) throw std::runtime_error("cannot open input");
    std::streamoff bytes = in.tellg();
    if (bytes <= 0 || bytes % sizeof(Trip)) throw std::runtime_error("invalid input length");
    std::vector<Trip> trips(bytes / sizeof(Trip));
    in.seekg(0);
    if (!in.read(reinterpret_cast<char*>(trips.data()), bytes)) throw std::runtime_error("short read");
    for (const auto& t : trips) if (t.hour < 0 || t.hour >= 24) throw std::runtime_error("invalid hour");
    std::cout << std::fixed << std::setprecision(7) << "load_s," << elapsed(before_load) << '\n';
    int stride = 1;
    if (mode == "omp") {
        omp_set_dynamic(0);
        omp_set_num_threads(threads);
        int actual = 0;
        #pragma omp parallel
        {
            #pragma omp single
            actual = omp_get_num_threads();
        }
        if (actual != threads) throw std::runtime_error("OpenMP team size mismatch");
        if (policy == "static") omp_set_schedule(omp_sched_static, 0);
        else if (policy == "dynamic") omp_set_schedule(omp_sched_dynamic, 1024);
        else if (policy == "guided") omp_set_schedule(omp_sched_guided, 1024);
        else throw std::runtime_error("unknown schedule");
    } else if (mode == "stride") {
        stride = std::stoi(policy);
        if (stride < 1) throw std::runtime_error("positive stride required");
    } else if (mode != "serial") throw std::runtime_error("unknown mode");
    Table result{};
    // First pass warms code, data and the runtime. Retain output so every pass is observable.
    for (int trial = 0; trial <= repeats; ++trial) {
        result = {};
        auto start = Clock::now();
        if (mode == "serial") sequential(trips, result);
        else if (mode == "omp") parallel(trips, result.data());
        else result[0].seconds = scan_stride(trips, stride);
        double seconds = elapsed(start);
        std::int64_t checksum = 0;
        for (const auto& row : result) checksum += row.direct + row.seconds;
        std::cout << (trial ? "trial," : "warmup,") << trial << ',' << seconds << ',' << checksum << '\n';
    }
    std::cout << "hour,trips,metered_m,direct_m,seconds\n";
    for (size_t h=0; h<result.size(); ++h) {
        const auto& r = result[h];
        std::cout << h << ',' << r.trips << ',' << r.metered << ',' << r.direct << ',' << r.seconds << '\n';
    }
} catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 1;
}
