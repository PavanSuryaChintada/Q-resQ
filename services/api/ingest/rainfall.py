"""Hourly precipitation from Open-Meteo's archive API, over a 0.05deg
grid across the bbox, for the last three monsoon seasons. Derives
antecedent accumulation windows (1/3/7/15 day) and max hourly
intensity per point - the rainfall TRIGGER inputs for docs/TRAINING.md
#5, not a static feature.

Parameterised by date range so the same function also serves a live/
forecast mode later (see docs/TRD.md #4) - not hardcoded to one event.
No key required.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import requests

from ingest.config import BBOX, DATA_RAW_DIR

OPENMETEO_URL = "https://archive-api.open-meteo.com/v1/archive"
OUTPUT_PATH = DATA_RAW_DIR / "rainfall_antecedent.parquet"

GRID_SPACING_DEG = 0.05
ANTECEDENT_WINDOWS_DAYS = [1, 3, 7, 15]

# Three most recent complete monsoon seasons (June-September) as of
# this build. Recomputed relative to "now" so this stays correct
# without manual updates each year the ingest is re-run.
_MONSOON_MONTHS = (6, 9)  # June through September, inclusive


def _monsoon_seasons(n_seasons: int = 3) -> list[tuple[str, str]]:
    today = pd.Timestamp.today()
    last_complete_year = today.year - 1 if today.month <= _MONSOON_MONTHS[1] else today.year
    seasons = []
    for year in range(last_complete_year, last_complete_year - n_seasons, -1):
        start = f"{year}-{_MONSOON_MONTHS[0]:02d}-01"
        end = pd.Timestamp(year=year, month=_MONSOON_MONTHS[1], day=1) + pd.offsets.MonthEnd(0)
        seasons.append((start, end.strftime("%Y-%m-%d")))
    return seasons


def _grid_points(bbox: tuple[float, float, float, float], spacing: float) -> tuple[np.ndarray, np.ndarray]:
    west, south, east, north = bbox
    lats = np.arange(south, north + spacing / 2, spacing)
    lons = np.arange(west, east + spacing / 2, spacing)
    lat_grid, lon_grid = np.meshgrid(lats, lons)
    return lat_grid.ravel(), lon_grid.ravel()


def _antecedent_windows(hourly_times: list[str], hourly_precip: list[float | None]) -> pd.DataFrame:
    """Daily accumulation, then rolling 1/3/7/15-day sums and max
    hourly intensity, per calendar day in the series.
    """
    df = pd.DataFrame({"time": pd.to_datetime(hourly_times), "precip_mm": hourly_precip}).fillna(0.0)
    df["date"] = df["time"].dt.date
    daily = df.groupby("date")["precip_mm"].sum().rename("rain_1d")
    max_hourly = df.groupby("date")["precip_mm"].max().rename("rain_intensity_max")

    out = pd.DataFrame({"rain_1d": daily, "rain_intensity_max": max_hourly})
    for days in ANTECEDENT_WINDOWS_DAYS:
        if days == 1:
            continue
        out[f"rain_{days}d"] = daily.rolling(window=days, min_periods=1).sum()
    return out.reset_index()


def fetch(n_seasons: int = 3, force: bool = False) -> None:
    if OUTPUT_PATH.exists() and not force:
        print(f"[rainfall] {OUTPUT_PATH} already exists, skipping (use --force to refetch)")
        return

    lats, lons = _grid_points(BBOX, GRID_SPACING_DEG)
    seasons = _monsoon_seasons(n_seasons)
    print(f"[rainfall] {len(lats)} grid points x {len(seasons)} monsoon seasons: {seasons}")

    all_rows = []
    for start_date, end_date in seasons:
        print(f"[rainfall] season {start_date} to {end_date}: fetching {len(lats)} points in one batched request")
        params = {
            "latitude": ",".join(f"{v:.3f}" for v in lats),
            "longitude": ",".join(f"{v:.3f}" for v in lons),
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "precipitation",
            "timezone": "UTC",
        }
        response = requests.get(OPENMETEO_URL, params=params, timeout=180)
        response.raise_for_status()
        payload = response.json()
        results = payload if isinstance(payload, list) else [payload]

        for point_result, lat, lon in zip(results, lats, lons):
            hourly = point_result.get("hourly", {})
            times = hourly.get("time", [])
            precip = hourly.get("precipitation", [])
            if not times:
                continue
            windows = _antecedent_windows(times, precip)
            windows["lat"] = lat
            windows["lon"] = lon
            windows["season_start"] = start_date
            all_rows.append(windows)

    if not all_rows:
        print("[rainfall] no data returned for any point/season - stopping without writing output")
        return

    df = pd.concat(all_rows, ignore_index=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"[rainfall] wrote {len(df)} rows ({len(lats)} points x {len(seasons)} seasons) to {OUTPUT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    fetch(n_seasons=args.seasons, force=args.force)
