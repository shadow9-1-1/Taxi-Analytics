
import csv
from pathlib import Path

path = Path("data/raw/yellow_tripdata_2015-01.csv")

print("File size (GB):", round(path.stat().st_size / 1e9, 2))

with path.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f)
    columns = next(reader)
    print("Columns:", columns)

    for i, row in enumerate(reader):
        print(row[:7])
        if i == 2:
            break
