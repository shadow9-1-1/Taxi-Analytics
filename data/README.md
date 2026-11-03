# January 2015 yellow taxi trips

Download `yellow_tripdata_2015-01.csv` from the [Kaggle NYC Yellow Taxi Trip Data collection](https://www.kaggle.com/datasets/elemento/nyc-yellow-taxi-trip-data) and place it in `data/raw/`. The publisher's [NYC TLC trip record page](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) describes the source. Use the historical CSV with endpoint coordinates. The experiment reads the Kaggle CSV version.

`samples/january-preview.csv` holds the header and first 50 raw records. For a quick pipeline check, use separate destinations to preserve the full-run results:

```sh
python preprocessing/Clean.py data/samples/january-preview.csv --out build/demo-data --results build/demo-results
```

The preprocessing command produces `100MB.bin`, `500MB.bin`, and `full.bin`. The subsets contain the first complete records fitting the given decimal byte budget. All three are local build products. Each 48-byte record contains five little-endian float64 values (pickup latitude and longitude, drop-off latitude and longitude, and metered miles) followed by two little-endian int32 values (local pickup hour and elapsed seconds). There is no header. A small input produces shorter subsets.
