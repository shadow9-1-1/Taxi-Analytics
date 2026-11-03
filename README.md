# Taxi Analytics

SW 401 Parallel and Distributed Systems · Phase 1 · Fall 2026  
Ahmed Wael and Seif Amr

How much farther did yellow taxis travel than the straight-line distance between their endpoints in January 2015? This project aggregates metered distance, great-circle distance, trip count and duration by pickup hour. Across 12,435,056 retained trips, the ratio of total metered to total direct distance was 1.383. Static OpenMP reduced full-month compute time from 425.0 ms sequentially to 77.2 ms with eight workers on the test laptop.

[Six-page report](report.pdf) · [Editable report](reports/Phase%201%20Report%20-%20Final.docx) · [Two-minute narrated demo](reports/phase-1-demo.mp4) · [Hourly results](results/reference.csv)

## Reproduce the run

Run commands from the repository root. The measured setup used Windows 11, MSYS2 UCRT64 GCC 16.2.0 with OpenMP, Python 3.13, pandas 2.3.3, NumPy 2.3.5 and Matplotlib 3.10.7. Have `g++`, its runtime DLLs and Python on PATH. On Linux, use GCC with libgomp and name the executable `build/taxi`.

1. Follow the [dataset instructions](data/README.md) to place the January CSV in `data/raw/`. Allow about 3.2 GB for raw and generated trip files, plus temporary space on reruns.
2. Set up dependencies and preprocess the month. The inspector prints the size, column names and example records. Cleaning writes three binaries and the independent reference table.

   ```powershell
   python -m pip install "pandas==2.3.3" "numpy==2.3.5" "matplotlib==3.10.7"
   python preprocessing/inspect_raw.py
   python preprocessing/Clean.py
   ```

3. Build and run the C++ baseline and OpenMP implementation.

   ```powershell
   New-Item -ItemType Directory -Force build | Out-Null
   g++ -O3 -std=c++17 -fopenmp src/taxi.cpp -o build/taxi.exe
   ./build/taxi.exe data/processed/full.bin serial 1 static 5
   ./build/taxi.exe data/processed/full.bin omp 8 static 5
   ```

   Both commands print load time, a warm-up, measured trials with checksums, and 24 hourly result rows. Distances are integer metres and durations are seconds. The [small sample](data/samples/january-preview.csv) can be used for a quick run by following the sample command in the data instructions and substituting `build/demo-data/full.bin` as input.

4. Reproduce the measurements, equality checks and figures.

   ```powershell
   python scripts/benchmark.py
   python scripts/scaled.py
   ```

   The benchmark checks each parallel output against the sequential result, the full sequential table against the independent reference, and every pass against its expected checksum. It writes [raw timings](results/timings.csv), [median times and metrics](results/summary.csv), and speedup and efficiency charts to `plots/`. The scaled experiment holds trips per worker constant and writes [its trials](results/scaled.csv). Rerunning replaces the recorded results and plots with local measurements.

## Memory and profiling experiments

The benchmark runs the stride experiment at 1, 8 and 64 records. To repeat the 64-record traversal or obtain a fresh serial gprof profile on the measured MSYS2 toolchain, run:

```powershell
./build/taxi.exe data/processed/full.bin stride 1 64 5
g++ -O3 -g -std=c++17 -fopenmp -pg -fno-inline '-Wl,--image-base,0x400000,--disable-dynamicbase,--disable-high-entropy-va' src/taxi.cpp -o build/taxi-prof.exe
Push-Location build
./taxi-prof.exe ../data/processed/full.bin serial 1 static 8 | Out-File ../results/profile-run.txt -Encoding ascii
gprof -b ./taxi-prof.exe gmon.out | Out-File ../results/gprof.txt -Encoding ascii
Pop-Location
```

On Linux omit the Windows linker options. The [recorded gprof output](results/gprof.txt) uses an instrumented executable. Release benchmark times come from the separate optimized executable above. The report discusses locality using measured traversal times. GNU gprof supplies function samples and calls.
