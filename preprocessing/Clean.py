"""Prepare fixed-width trip files and an independent hourly reference from the CSV."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

FIELDS = ["pickup_latitude", "pickup_longitude", "dropoff_latitude", "dropoff_longitude", "trip_distance"]
TIMES = ["tpep_pickup_datetime", "tpep_dropoff_datetime"]
LAYOUT = np.dtype([(k, "<f8") for k in FIELDS] + [("hour", "<i4"), ("seconds", "<i4")])


def prepare(source, out, results):
    out.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    counts = dict(raw=0, bad_time=0, bad_location=0, bad_distance=0, kept=0)
    totals = np.zeros((24, 4), dtype=np.int64)
    limits = {"100MB": 100_000_000 // LAYOUT.itemsize, "500MB": 500_000_000 // LAYOUT.itemsize}
    with (out / "full.bin.tmp").open("wb") as dest:
        for frame in pd.read_csv(source, usecols=TIMES + FIELDS, dtype=str, chunksize=200_000):
            counts["raw"] += len(frame)
            start, end = [pd.to_datetime(frame[k], format="%Y-%m-%d %H:%M:%S", errors="coerce") for k in TIMES]
            duration = (end - start).dt.total_seconds()
            valid = (start >= "2015-01-01") & (start < "2015-02-01") & duration.between(1, 86400)
            counts["bad_time"] += int((~valid).sum())
            nums = frame[FIELDS].apply(pd.to_numeric, errors="coerce")
            location = (nums.pickup_latitude.between(40, 42) & nums.dropoff_latitude.between(40, 42)
                        & nums.pickup_longitude.between(-75, -72) & nums.dropoff_longitude.between(-75, -72))
            counts["bad_location"] += int((valid & ~location).sum())
            valid &= location
            distance = nums.trip_distance.between(0, 200, inclusive="right")
            counts["bad_distance"] += int((valid & ~distance).sum())
            valid &= distance
            records = np.empty(int(valid.sum()), dtype=LAYOUT)
            for col in FIELDS:
                records[col] = nums.loc[valid, col]
            h = start[valid].dt.hour.to_numpy(dtype=int)
            records["hour"], records["seconds"] = h, duration[valid]
            records.tofile(dest)
            counts["kept"] += len(records)
            # Spherical central angle using atan2, independent of the C++ asin path.
            la, lo, lb, lp = (np.deg2rad(records[col]) for col in FIELDS[:4])
            a = np.sin((lb-la)/2)**2 + np.cos(la)*np.cos(lb)*np.sin((lp-lo)/2)**2
            air = 12_742_000 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
            for j, weights in enumerate([None, np.floor(records["trip_distance"]*1609.344+0.5),
                                         np.floor(air+0.5), records["seconds"]]):
                totals[:, j] += np.bincount(h, weights=weights, minlength=24).astype(np.int64)
    full = out / "full.bin"
    (out / "full.bin.tmp").replace(full)
    for name, rows in limits.items():
        with full.open("rb") as src, (out / (name + ".bin")).open("wb") as dest:
            remaining = min(rows, counts["kept"]) * LAYOUT.itemsize
            while remaining:
                block = src.read(min(remaining, 4*1024*1024))
                dest.write(block)
                remaining -= len(block)
    table = pd.DataFrame(totals, columns=["trips", "metered_m", "direct_m", "seconds"])
    table.to_csv(results / "reference.csv", index_label="hour")
    counts["raw_bytes"] = source.stat().st_size
    counts["processed_bytes"] = full.stat().st_size
    (results / "cleaning.json").write_text(json.dumps(counts, indent=2))
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", type=Path, default=Path("data/raw/yellow_tripdata_2015-01.csv"))
    parser.add_argument("--out", type=Path, default=Path("data/processed"))
    parser.add_argument("--results", type=Path, default=Path("results"))
    args = parser.parse_args()
    prepare(args.source, args.out, args.results)
