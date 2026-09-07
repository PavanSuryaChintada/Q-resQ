"""NASA Global Landslide Catalog -> data/raw/landslides.geojson.

The catalogue is sparse. docs/DATA.md #5 says to pad the search area
to the whole of Mizoram and neighbouring districts to get a usable
label count, and to report the strict-bbox and padded-region counts
separately so the real local label scarcity isn't hidden. This is
disclosed transfer, not silently different data - docs/TRAINING.md
#3 makes the same call for training labels.
"""

from __future__ import annotations

import argparse
import io
import time

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

from ingest.config import BBOX, DATA_RAW_DIR

_MAX_RETRIES = 4
_RETRY_BACKOFF_S = 20

GLC_CSV_URL = (
    "https://data.nasa.gov/docs/legacy/Global_Landslide_Catalog_Export/"
    "Global_Landslide_Catalog_Export_rows.csv"
)
OUTPUT_PATH = DATA_RAW_DIR / "landslides.geojson"

# Whole of Mizoram plus a buffer into neighbouring Assam/Manipur/Tripura -
# (west, south, east, north) in EPSG:4326 degrees. Wider than the strict
# district bbox in ingest.config.BBOX on purpose; see module docstring.
PADDED_BBOX = (91.50, 21.50, 94.00, 25.00)

KEEP_COLUMNS = [
    "event_date", "landslide_trigger", "landslide_size", "landslide_category",
    "fatality_count", "injury_count", "location_description",
]


def _within(lon: pd.Series, lat: pd.Series, bbox: tuple[float, float, float, float]) -> pd.Series:
    west, south, east, north = bbox
    return (lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)


def fetch(force: bool = False) -> None:
    if OUTPUT_PATH.exists() and not force:
        print(f"[landslides] {OUTPUT_PATH} already exists, skipping (use --force to refetch)")
        return

    print(f"[landslides] downloading {GLC_CSV_URL}")
    response = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.get(GLC_CSV_URL, timeout=60)
            response.raise_for_status()
            break
        except Exception as exc:  # noqa: BLE001 - transient network errors, retry
            is_last = attempt == _MAX_RETRIES
            print(f"[landslides] attempt {attempt}/{_MAX_RETRIES} failed: {exc}")
            if is_last:
                raise
            print(f"[landslides] retrying in {_RETRY_BACKOFF_S}s")
            time.sleep(_RETRY_BACKOFF_S)
    df = pd.read_csv(io.StringIO(response.text))
    print(f"[landslides] catalogue has {len(df)} global records")

    df = df.dropna(subset=["longitude", "latitude"])
    strict_mask = _within(df["longitude"], df["latitude"], BBOX)
    padded_mask = _within(df["longitude"], df["latitude"], PADDED_BBOX)

    strict_count = int(strict_mask.sum())
    padded_count = int(padded_mask.sum())
    print(f"[landslides] {strict_count} records inside the strict Aizawl district bbox {BBOX}")
    print(f"[landslides] {padded_count} records inside the padded Mizoram+neighbours bbox {PADDED_BBOX}")

    subset = df[padded_mask].copy()
    if subset.empty:
        print("[landslides] no records found even in the padded region - writing an empty file")

    keep = [c for c in KEEP_COLUMNS if c in subset.columns]
    subset = subset[keep + ["longitude", "latitude"]]
    geometry = [Point(lon, lat) for lon, lat in zip(subset["longitude"], subset["latitude"])]
    gdf = gpd.GeoDataFrame(subset.drop(columns=["longitude", "latitude"]), geometry=geometry, crs="EPSG:4326")
    gdf["in_strict_bbox"] = strict_mask[padded_mask].to_numpy()

    gdf.to_file(OUTPUT_PATH, driver="GeoJSON")
    print(f"[landslides] wrote {len(gdf)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    fetch(force=args.force)
