"""Time static OpenMP with 1/8 of the cleaned month per worker."""
import csv
import os
import statistics
import subprocess
import tempfile
from pathlib import Path

source = Path("data/processed/full.bin")
exe = "./build/taxi.exe" if os.name == "nt" else "./build/taxi"
per_worker = source.stat().st_size // (48*8)
with tempfile.TemporaryDirectory(dir="build") as tmp, open("results/scaled.csv","w",newline="") as out:
    writer = csv.writer(out)
    writer.writerow(["threads","rows","trial","seconds","median_s"])
    for p in [1,2,4,8]:
        n = per_worker*p
        path = Path(tmp)/"prefix.bin"
        with source.open("rb") as src, path.open("wb") as dest:
            remaining = n*48
            while remaining:
                block = src.read(min(remaining, 8*1024*1024))
                dest.write(block)
                remaining -= len(block)
        log = subprocess.check_output([exe,str(path),"omp",str(p),"static","5"],text=True)
        times = [float(line.split(",")[2]) for line in log.splitlines() if line.startswith("trial,")]
        for i,t in enumerate(times,1):
            writer.writerow([p,n,i,t,statistics.median(times)])
