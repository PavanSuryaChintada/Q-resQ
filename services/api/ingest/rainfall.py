"""Rainfall from two keyless sources, on a coarse grid across the
bbox. Both parameterised by date range (reusable for a live forecast
mode later - not hardcoded to 2018).
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import pandas as pd
import requests

from ingest.config import BBOX, DATA_RAW_DIR, DEFAULT_EVENT_END, DEFAULT_EVENT_START

OPENMETEO_URL = "https://archive-api.open-meteo.com/v1/archive"
NASAPOWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

OPENMETEO_OUTPUT = DATA_RAW_DIR / "rainfall_openmeteo_2018.parquet"
NASAPOWER_OUTPUT = DATA_RAW_DIR / "rainfall_nasapower_2018.parquet"

GRID_SPACING_DEG = 0.1
_NASAPOWER_REQUEST_DELAY_S = 1.0


def _grid_points(bbox: tuple[float, float, float, float], spacing: float) -> tuple[np.ndarray, np.ndarray]:
    west, south, east, north = bbox
    lats = np.arange(south, north + spacing / 2, spacing)
    lons = np.arange(west, east + spacing / 2, spacing)
    lat_grid, lon_grid = np.meshgrid(lats, lons)
    return lat_grid.ravel(), lon_grid.ravel()


def fetch_openmeteo(start_date: str = DEFAULT_EVENT_START, end_date: str = DEFAULT_EVENT_END,
                     force: bool = False) -> None:
    if OPENMETEO_OUTPUT.exists() and not force:
        print(f"[rainfall] {OPENMETEO_OUTPUT} already exists, skipping (use --force to refetch)")
        return

    lats, lons = _grid_points(BBOX, GRID_SPACING_DEG)
    print(f"[rainfall] open-meteo: {len(lats)} points, {start_date} to {end_date}, single batched request")

    params = {
        "latitude": ",".join(f"{v:.2f}" for v in lats),
        "longitude": ",".join(f"{v:.2f}" for v in lons),
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "precipitation",
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
        precip = hourly.get("precipitation", [])
        for t, p in zip(times, precip):
            rows.append({"lat": lat, "lon": lon, "time": t, "precipitation_mm": p})

    df = pd.DataFrame(rows)
    df.to_parquet(OPENMETEO_OUTPUT, index=False)
    print(f"[rainfall] wrote {len(df)} rows ({len(lats)} points) to {OPENMETEO_OUTPUT}")


def fetch_nasapower(start_date: str = DEFAULT_EVENT_START, end_date: str = DEFAULT_EVENT_END,
                     force: bool = False) -> None:
    if NASAPOWER_OUTPUT.exists() and not force:
        print(f"[rainfall] {NASAPOWER_OUTPUT} already exists, skipping (use --force to refetch)")
        return

    lats, lons = _grid_points(BBOX, GRID_SPACING_DEG)
    start_compact = start_date.replace("-", "")
    end_compact = end_date.replace("-", "")
    print(f"[rainfall] nasa power: {len(lats)} points, {start_date} to {end_date}, "
          f"one request per point (no multi-point endpoint)")

    rows = []
    for i, (lat, lon) in enumerate(zip(lats, lons)):
        params = {
            "parameters": "PRECTOTCORR",
            "community": "AG",
            "longitude": lon,
            "latitude": lat,
            "start": start_compact,
            "end": end_compact,
            "format": "JSON",
        }
        try:
            response = requests.get(NASAPOWER_URL, params=params, timeout=60)
            response.raise_for_status()
            daily = response.json()["properties"]["parameter"]["PRECTOTCORR"]
            for date_str, value in daily.items():
                rows.append({"lat": lat, "lon": lon, "date": date_str, "precip_mm": value})
        except Exception as exc:  # noqa: BLE001 - keep going, report at the end
            print(f"[rainfall]   point {i+1}/{len(lats)} ({lat:.2f},{lon:.2f}) failed: {exc}")
            continue

        if (i + 1) % 20 == 0 or i + 1 == len(lats):
            print(f"[rainfall]   {i+1}/{len(lats)} points done")
        time.sleep(_NASAPOWER_REQUEST_DELAY_S)

    df = pd.DataFrame(rows)
    df.to_parquet(NASAPOWER_OUTPUT, index=False)
    print(f"[rainfall] wrote {len(df)} rows to {NASAPOWER_OUTPUT}")


def fetch(start_date: str = DEFAULT_EVENT_START, end_date: str = DEFAULT_EVENT_END, force: bool = False) -> None:
    fetch_openmeteo(start_date, end_date, force=force)
    fetch_nasapower(start_date, end_date, force=force)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=DEFAULT_EVENT_START)
    parser.add_argument("--end", default=DEFAULT_EVENT_END)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    fetch(start_date=args.start, end_date=args.end, force=args.force)
