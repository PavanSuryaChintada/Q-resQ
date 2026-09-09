"""Rainfall/soil-moisture inputs for the trigger index (docs/TRAINING.md #5).

Intended sources: NASA GPM IMERG (recent rainfall), IMD RF25 (historical),
ERA5-Land (soil moisture). **None of those are wired up yet** -
fetch_era5_rainfall/fetch_soil_moisture below generate randomised
monsoon-shaped values (rng.uniform, seeded), not real satellite/reanalysis
data. Every value this module returns is synthetic until the TODOs in
those two functions are done - this is disclosed here and in
risk/features.py's log line, not presented as real.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from ingest.config import DATA_RAW_DIR

DATA_DIR = DATA_RAW_DIR / "rainfall"
DATA_DIR.mkdir(exist_ok=True)

# Aizawl coordinates for data fetching
AIZAWAL_COORDS = {
    "lat": 23.736,
    "lon": 92.717
}

# Aizawl district bounding box (from config.py)
AIZAWAL_BBOX = {
    "west": 92.4,
    "south": 23.5,
    "east": 92.9,
    "north": 23.9
}


def fetch_era5_rainfall(start_date: str, end_date: str) -> xr.Dataset:
    """Fetch ERA5 rainfall data for Aizawl region.

    Uses ERA5-Land which provides daily precipitation at 0.1 deg resolution.
    """
    print(f"[rainfall] generating SYNTHETIC ERA5-shaped rainfall from {start_date} to {end_date} (no real API wired up)")

    bbox = AIZAWAL_BBOX
    lat_range = slice(bbox["south"], bbox["north"])
    lon_range = slice(bbox["west"], bbox["east"])

    # TODO: Integrate with actual ERA5 API or CDS
    # For now, create synthetic data based on realistic monsoon patterns
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    n_days = len(dates)

    # Create grid
    lat = np.linspace(bbox["south"], bbox["north"], 50)
    lon = np.linspace(bbox["west"], bbox["east"], 50)

    # Generate realistic monsoon rainfall patterns
    rng = np.random.RandomState(42)
    rainfall = np.zeros((n_days, len(lat), len(lon)))

    for i, date in enumerate(dates):
        # Monsoon season (June-September) has higher rainfall
        if 6 <= date.month <= 9:
            base_rainfall = rng.uniform(5, 30, (len(lat), len(lon)))
            # Add some spatial variation
            rainfall[i] = base_rainfall * (1 + 0.3 * rng.randn(len(lat), len(lon)))
        else:
            rainfall[i] = rng.uniform(0, 5, (len(lat), len(lon)))

    # Create xarray dataset
    ds = xr.Dataset(
        {
            "precipitation": (["time", "lat", "lon"], rainfall),
        },
        coords={
            "time": dates,
            "lat": lat,
            "lon": lon,
        }
    )

    output_path = DATA_DIR / "era5_rainfall.nc"
    ds.to_netcdf(output_path)
    print(f"[rainfall] wrote ERA5 data to {output_path}")
    return ds


def fetch_soil_moisture(start_date: str, end_date: str) -> xr.Dataset:
    """Fetch soil moisture data from SMAP/ERA5-Land.

    Soil moisture is critical for landslide triggering as it affects
    pore pressure in slopes.
    """
    print(f"[rainfall] generating SYNTHETIC soil moisture from {start_date} to {end_date} (no real API wired up)")

    bbox = AIZAWAL_BBOX
    lat_range = slice(bbox["south"], bbox["north"])
    lon_range = slice(bbox["west"], bbox["east"])

    # TODO: Integrate with SMAP API or ERA5-Land
    # For now, create synthetic data
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    n_days = len(dates)

    lat = np.linspace(bbox["south"], bbox["north"], 50)
    lon = np.linspace(bbox["west"], bbox["east"], 50)

    rng = np.random.RandomState(42)
    # Soil moisture typically 0.2-0.4 volumetric, higher during monsoon
    soil_moisture = np.zeros((n_days, len(lat), len(lon)))

    for i, date in enumerate(dates):
        if 6 <= date.month <= 9:
            base_moisture = rng.uniform(0.25, 0.40, (len(lat), len(lon)))
        else:
            base_moisture = rng.uniform(0.15, 0.30, (len(lat), len(lon)))
        soil_moisture[i] = base_moisture

    ds = xr.Dataset(
        {
            "soil_moisture": (["time", "lat", "lon"], soil_moisture),
        },
        coords={
            "time": dates,
            "lat": lat,
            "lon": lon,
        }
    )

    output_path = DATA_DIR / "soil_moisture.nc"
    ds.to_netcdf(output_path)
    print(f"[rainfall] wrote soil moisture data to {output_path}")
    return ds


_era5_cache: xr.Dataset | None = None
_soil_moisture_cache: xr.Dataset | None = None


def _load_era5() -> xr.Dataset | None:
    """Open era5_rainfall.nc once and keep it in memory. Calling
    xr.open_dataset per grid cell (284k times for the district grid)
    was the previous behaviour here and made any risk-cell rebuild take
    10+ minutes - this cache is what fixes that, not a data change.
    """
    global _era5_cache
    if _era5_cache is None:
        era5_path = DATA_DIR / "era5_rainfall.nc"
        if not era5_path.exists():
            return None
        _era5_cache = xr.open_dataset(era5_path).load()
    return _era5_cache


def _load_soil_moisture() -> xr.Dataset | None:
    global _soil_moisture_cache
    if _soil_moisture_cache is None:
        soil_path = DATA_DIR / "soil_moisture.nc"
        if not soil_path.exists():
            return None
        _soil_moisture_cache = xr.open_dataset(soil_path).load()
    return _soil_moisture_cache


def get_rainfall_for_cell(lat: float, lon: float, days_back: int = 15) -> dict[str, float]:
    """Get rainfall metrics for a specific cell.

    Returns:
        Dict with rain_15d, rain_3d, rain_intensity_max
    """
    ds = _load_era5()
    if ds is None:
        print(f"[rainfall] ERA5 data not found, using synthetic values")
        return {
            "rain_15d": 0.5,
            "rain_3d": 0.4,
            "rain_intensity_max": 0.3,
        }

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    # Select data for date range
    ds_slice = ds.sel(time=slice(start_date, end_date))

    # Find nearest grid point
    lat_idx = abs(ds.lat.values - lat).argmin()
    lon_idx = abs(ds.lon.values - lon).argmin()

    # Extract time series
    precip = ds_slice.precipitation[:, lat_idx, lon_idx].values

    # Calculate metrics
    rain_15d = float(np.sum(precip))
    rain_3d = float(np.sum(precip[-3:])) if len(precip) >= 3 else rain_15d
    rain_intensity_max = float(np.max(precip)) if len(precip) > 0 else 0.0

    return {
        "rain_15d": rain_15d,
        "rain_3d": rain_3d,
        "rain_intensity_max": rain_intensity_max,
    }


def get_soil_moisture_for_cell(lat: float, lon: float) -> float:
    """Get current soil moisture for a specific cell."""
    ds = _load_soil_moisture()
    if ds is None:
        print(f"[rainfall] Soil moisture data not found, using synthetic value")
        return 0.5

    # Find nearest grid point
    lat_idx = abs(ds.lat.values - lat).argmin()
    lon_idx = abs(ds.lon.values - lon).argmin()

    # Get most recent value
    return float(ds.soil_moisture[-1, lat_idx, lon_idx].values)


def get_rainfall_grid(lats: np.ndarray, lons: np.ndarray, days_back: int = 15) -> dict[str, np.ndarray]:
    """Vectorised equivalent of calling get_rainfall_for_cell once per
    point. Calling the per-cell version in a Python loop over a 284k-cell
    district grid re-runs xarray's label-based .sel()/argmin() that many
    times and takes 10+ minutes; this does the same nearest-neighbour
    lookup as one batch of numpy operations.
    """
    n = len(lats)
    ds = _load_era5()
    if ds is None:
        print("[rainfall] ERA5 data not found, using synthetic values")
        return {
            "rain_15d": np.full(n, 0.5),
            "rain_3d": np.full(n, 0.4),
            "rain_intensity_max": np.full(n, 0.3),
        }

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    ds_slice = ds.sel(time=slice(start_date, end_date))
    precip = ds_slice.precipitation.values  # (time, lat, lon)

    ds_lats = ds.lat.values
    ds_lons = ds.lon.values
    lat_idx = np.abs(ds_lats[:, None] - lats[None, :]).argmin(axis=0)
    lon_idx = np.abs(ds_lons[:, None] - lons[None, :]).argmin(axis=0)

    selected = precip[:, lat_idx, lon_idx]  # (time, n_cells)
    rain_15d = selected.sum(axis=0)
    rain_3d = selected[-3:].sum(axis=0) if selected.shape[0] >= 3 else rain_15d.copy()
    rain_intensity_max = selected.max(axis=0) if selected.shape[0] > 0 else np.zeros(n)

    return {
        "rain_15d": rain_15d.astype(float),
        "rain_3d": rain_3d.astype(float),
        "rain_intensity_max": rain_intensity_max.astype(float),
    }


def get_soil_moisture_grid(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Vectorised equivalent of get_soil_moisture_for_cell - see
    get_rainfall_grid's docstring for why this exists.
    """
    ds = _load_soil_moisture()
    if ds is None:
        print("[rainfall] Soil moisture data not found, using synthetic value")
        return np.full(len(lats), 0.5)

    ds_lats = ds.lat.values
    ds_lons = ds.lon.values
    lat_idx = np.abs(ds_lats[:, None] - lats[None, :]).argmin(axis=0)
    lon_idx = np.abs(ds_lons[:, None] - lons[None, :]).argmin(axis=0)
    return ds.soil_moisture.values[-1, lat_idx, lon_idx].astype(float)


if __name__ == "__main__":
    # Fetch last 30 days of data
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    fetch_era5_rainfall(start_date, end_date)
    fetch_soil_moisture(start_date, end_date)
