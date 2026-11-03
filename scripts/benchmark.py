"""Run from the project root after building taxi and preprocessing the monthly file."""
import argparse
import csv
import io
import os
from pathlib import Path
from statistics import median
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def save(name, rows):
    with (Path("results") / name).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(exe, size, mode, threads, policy):
    raw = subprocess.check_output([exe, f"data/processed/{size}.bin", mode, str(threads), policy, "5"], text=True)
    prefix, table = raw.split("hour,trips,metered_m,direct_m,seconds\n")
    return list(csv.reader(io.StringIO(prefix))), list(csv.reader(io.StringIO(table)))


def main(exe):
    trials, summary = [], []
    ref = list(csv.reader(Path("results/reference.csv").read_text().splitlines()))[1:]
    for size in ["100MB", "500MB", "full"]:
        cases = [("serial", 1, "static")] + [("omp", t, "static") for t in [1, 2, 4, 8]]
        if size == "full":
            cases += [("omp", 8, policy) for policy in ["dynamic", "guided"]]
            cases += [("stride", 1, str(s)) for s in [1, 8, 64]]
        for mode, p, policy in cases:
            logs, table = run(exe, size, mode, p, policy)
            if mode == "serial":
                expected = table
                if size == "full" and expected != ref:
                    raise ValueError("full baseline differs from preprocessing reference")
            elif mode == "omp" and table != expected:
                raise ValueError("parallel histogram differs from serial")
            expected_sum = sum(int(r[4]) + (0 if mode == "stride" else int(r[3])) for r in expected)
            times = []
            for tag, *data in logs:
                if tag == "load_s":
                    load = float(data[0])
                    continue
                repeat, seconds, checksum = data
                if int(checksum) != expected_sum:
                    raise ValueError("trial checksum mismatch")
                if tag == "trial":
                    times.append(float(seconds))
                    trials.append(dict(dataset=size, mode=mode, threads=p, schedule=policy, repeat=repeat,
                                       seconds=seconds, checksum=checksum))
            runtime = median(times)
            if mode == "serial":
                baseline = runtime
            speedup = baseline/runtime
            summary.append(dict(dataset=size, mode=mode, threads=p, schedule=policy, median_s=runtime,
                                load_s=load, speedup=speedup if mode!="stride" else "",
                                efficiency=speedup/p if mode!="stride" else "",
                                serial_fraction=(p/speedup-1)/(p-1) if p>1 else ""))
            print(size, mode, p, policy, runtime, flush=True)
    save("timings.csv", trials)
    save("summary.csv", summary)
    plot(summary)


def plot(summary):
    Path("plots").mkdir(exist_ok=True)
    for field, ylabel in [("speedup", "Speedup (times sequential)"), ("efficiency", "Parallel efficiency (%)")]:
        fig, ax = plt.subplots(figsize=(7.3, 3.05), layout="constrained")
        for size, color, marker in [("100MB", "#98703c", "s"), ("500MB", "#426da1", "^"), ("full", "#00776e", "o")]:
            rows = [r for r in summary if r["dataset"]==size and r["mode"]=="omp" and r["schedule"]=="static"]
            ax.plot([r["threads"] for r in rows], [r[field]*(100 if field=="efficiency" else 1) for r in rows],
                    marker=marker, color=color, label=("Full" if size == "full" else size.replace("MB", " MB")))
        ax.set(xticks=[1,2,4,8], xlabel="OpenMP threads", ylabel=ylabel, ylim=(0,None))
        ax.grid(axis="y", alpha=.25)
        ax.spines[["right","top"]].set_visible(False)
        ax.legend(frameon=False, ncol=3)
        fig.savefig(f"plots/{field}.png", dpi=180)
        plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", default="./build/taxi.exe" if os.name=="nt" else "./build/taxi")
    main(parser.parse_args().exe)
