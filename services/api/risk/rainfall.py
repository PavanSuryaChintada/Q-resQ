"""rain_24h/72h/7d from IMD RF25 gridded daily rainfall.

docs/TRD.md #3 lists NASA POWER as the source; this project uses the
user-supplied IMD RF25 NetCDF instead (0.25 deg, India, daily) - the
authoritative source for India and already in hand. Joined at
inference, not stored per cell, matching the documented data flow.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr


def load_rainfall_dataset(nc_path: str) -> xr.Dataset:
    return xr.open_dataset(nc_path)


def rain_window(ds: xr.Dataset, lat: float, lon: float, end_date: str, days: int) -> float:
    """Sum of daily rainfall over `days` days ending on end_date (inclusive)."""
    end = pd.Timestamp(end_date)
    start = end - pd.Timedelta(days=days - 1)
    subset = ds.RAINFALL.sel(LATITUDE=lat, LONGITUDE=lon, method="nearest").sel(TIME=slice(start, end))
    return float(subset.sum())


def rain_window_grid(ds: xr.Dataset, lats: np.ndarray, lons: np.ndarray,
                      end_date: str, days: int) -> np.ndarray:
    """Vectorised rain_window for many points at once."""
    end = pd.Timestamp(end_date)
    start = end - pd.Timedelta(days=days - 1)
    windowed = ds.RAINFALL.sel(TIME=slice(start, end)).sum(dim="TIME")

    lat_da = xr.DataArray(np.asarray(lats), dims="points")
    lon_da = xr.DataArray(np.asarray(lons), dims="points")
    sampled = windowed.sel(LATITUDE=lat_da, LONGITUDE=lon_da, method="nearest")
    return sampled.values
