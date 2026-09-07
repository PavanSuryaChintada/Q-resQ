"""rain_24h/72h/7d from a gridded historical rainfall NetCDF.

docs/TRD.md #4 describes antecedent 1/3/7/15-day windows plus max
intensity from Open-Meteo/IMD for the NER build - that ingest and the
antecedent-window functions are a later sub-project (docs/DATA.md).
This module currently only has the historical-lookup helpers carried
from the flood build; the live-forecast "what if today" functions
that used to live here were deleted with the Srikakulam-specific
live-risk-check feature (docs/MIGRATION.md #5).
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
