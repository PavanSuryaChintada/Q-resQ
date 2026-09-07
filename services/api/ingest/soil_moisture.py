"""Soil moisture from Open-Meteo's ERA5-Land archive (soil_moisture_0_to_7cm,
volumetric, m3/m3), over the same coarse grid as rainfall.py.

docs/DATA.md #7 asks for NASA SMAP L3, falling back to ERA5-Land "if
SMAP is awkward" - SMAP requires a NASA Earthdata login, the same
credential being set up separately for the Sentinel-1 SLC download
(docs/DATA.md Part 2.A), which this ingest session does not have. This
uses the documented ERA5-Land fallback instead, not a silent
substitution: coarse (~9km native, 0.05deg grid here) and disclosed as
such, matching the source note this function requires.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import requests
import xarray as xr

from ingest.config import BBOX, DATA_RAW_DIR

OPENMETEO_URL = "https://archive-api.open-meteo.com/v1/archive"
OUTPUT_PATH = DATA_RAW_DIR / "soil_moisture.nc"

GRID_SPACING_DEG = 0.05
LOOKBACK_DAYS = 90  # matches Open-Meteo's own forecast-mode window (rainfall.py's live-mode sibling)


def _grid_points(bbox: tuple[float, float, float, float], spacing: float) -> tuple[np.ndarray, np.ndarray]:
    west, south, east, north = bbox
    lats = np.arange(south, north + spacing / 2, spacing)
    lons = np.arange(west, east + spacing / 2, spacing)
    lat_grid, lon_grid = np.meshgrid(lats, lons)
    return lat_grid.ravel(), lon_grid.ravel()


def fetch(force: bool = False) -> None:
    if OUTPUT_PATH.exists() and not force:
        print(f"[soil_moisture] {OUTPUT_PATH} already exists, skipping (use --force to refetch)")
        return

    lats, lons = _grid_points(BBOX, GRID_SPACING_DEG)
    end_date = pd.Timestamp.today().normalize() - pd.Timedelta(days=6)  # ERA5-Land has a short ingest lag
    start_date = end_date - pd.Timedelta(days=LOOKBACK_DAYS)
    print(f"[soil_moisture] era5-land: {len(lats)} points, {start_date.date()} to {end_date.date()}")

    params = {
        "latitude": ",".join(f"{v:.3f}" for v in lats),
        "longitude": ",".join(f"{v:.3f}" for v in lons),
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "hourly": "soil_moisture_0_to_7cm",
        "models": "era5_land",
        "timezone": "UTC",
    }
    response = requests.get(OPENMETEO_URL, params=params, timeout=180)
    response.raise_for_status()
    payload = response.json()
    results = payload if isinstance(payload, list) else [payload]

    rows = []
    for point_result, lat, lon in zip(results, lats, lons):
        hourly = point_result.get("hourly", {})
        times = hourly.get("time", [])
        values = hourly.get("soil_moisture_0_to_7cm", [])
        for t, v in zip(times, values):
            rows.append({"lat": lat, "lon": lon, "time": t, "soil_moisture_m3m3": v})

    if not rows:
        print("[soil_moisture] no data returned - stopping without writing output")
        return

    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"])
    ds = df.set_index(["time", "lat", "lon"]).to_xarray()
    ds.attrs["source"] = "Open-Meteo ERA5-Land reanalysis (soil_moisture_0_to_7cm)"
    ds.attrs["resolution"] = "~9km native (ERA5-Land), resampled to a 0.05deg query grid here"
    ds.attrs["note"] = (
        "Fallback from NASA SMAP per docs/DATA.md #7: SMAP requires a NASA "
        "Earthdata login not available to this ingest run. Coarse resolution "
        "is expected and disclosed, not fabricated precision."
    )
    ds.to_netcdf(OUTPUT_PATH)
    print(f"[soil_moisture] wrote {len(df)} rows ({len(lats)} points) to {OUTPUT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    fetch(force=args.force)
