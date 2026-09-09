"""Aizawl-specific landslide inventory -> data/raw/landslides.geojson.

Uses the 19-event Aizawl landslide inventory (2016-2025) compiled from
GSI Bhukosh data, published literature, and government reports.
Data source: "Frictional timescales of landslides in Mizoram under climate extremes"
(Sarma et al., 2026) - https://doi.org/10.5281/zenodo.20783994

This replaces the sparse NASA Global Landslide Catalog with region-specific
data that provides sufficient labels for ML training.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from ingest.config import DATA_RAW_DIR

OUTPUT_PATH = DATA_RAW_DIR / "landslides.geojson"
LOCAL_CSV_PATH = DATA_RAW_DIR / "landslides_aizawl.csv"


def fetch(force: bool = False) -> None:
    if OUTPUT_PATH.exists() and not force:
        print(f"[landslides] {OUTPUT_PATH} already exists, skipping (use --force to refetch)")
        return

    # Load the local Aizawl landslide inventory
    if not LOCAL_CSV_PATH.exists():
        print(f"[landslides] {LOCAL_CSV_PATH} not found - create it first")
        return

    print(f"[landslides] loading Aizawl inventory from {LOCAL_CSV_PATH}")
    df = pd.read_csv(LOCAL_CSV_PATH, dtype={"event_id": str})
    print(f"[landslides] loaded {len(df)} landslide events (2016-2025)")

    # Convert to GeoDataFrame
    geometry = [Point(lon, lat) for lon, lat in zip(df["lon"], df["lat"])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

    # Mark all as within strict bbox (this is Aizawl-specific data)
    gdf["in_strict_bbox"] = True

    # Rename columns to match expected format
    column_mapping = {
        "date": "event_date",
        "failure_type": "landslide_category",
        "fatalities": "fatality_count",
        "notes": "location_description",
    }
    gdf = gdf.rename(columns=column_mapping)

    # Add missing columns for compatibility
    if "landslide_trigger" not in gdf.columns:
        gdf["landslide_trigger"] = "rainfall"  # All events are rainfall-triggered
    if "landslide_size" not in gdf.columns:
        gdf["landslide_size"] = "medium"  # Default size
    if "injury_count" not in gdf.columns:
        gdf["injury_count"] = 0  # Not reported in inventory

    # Select relevant columns
    keep_columns = [
        "event_date", "landslide_trigger", "landslide_size", "landslide_category",
        "fatality_count", "injury_count", "location_description", "source",
        "depth_m", "event_id", "in_strict_bbox"
    ]
    available_columns = [c for c in keep_columns if c in gdf.columns]
    gdf = gdf[available_columns + ["geometry"]]

    gdf.to_file(OUTPUT_PATH, driver="GeoJSON")
    print(f"[landslides] wrote {len(gdf)} records to {OUTPUT_PATH}")
    print(f"[landslides] source: GSI + published literature + government reports")
    print(f"[landslides] period: 2016-2025, includes Cyclone Remal cluster (May 28, 2024)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    fetch(force=args.force)
