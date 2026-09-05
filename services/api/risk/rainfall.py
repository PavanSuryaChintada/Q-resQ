"""rain_24h/72h/7d from IMD RF25 gridded daily rainfall.

docs/TRD.md #3 lists NASA POWER as the source; this project uses the
user-supplied IMD RF25 NetCDF instead (0.25 deg, India, daily) - the
authoritative source for India and already in hand. Joined at
inference, not stored per cell, matching the documented data flow.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import date as date_cls

import numpy as np
import pandas as pd
import xarray as xr

_OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}&daily=precipitation_sum"
    "&past_days=92&forecast_days=16&timezone=auto"
)


def _fetch_daily(lat: float, lon: float) -> tuple[list[str], list[float | None]]:
    url = _OPEN_METEO_URL.format(lat=lat, lon=lon)
    with urllib.request.urlopen(url, timeout=10) as response:
        payload = json.load(response)
    return payload["daily"]["time"], payload["daily"]["precipitation_sum"]


def live_rain_date_range(lat: float, lon: float) -> tuple[str, str]:
    """The (min, max) date Open-Meteo currently has data for, so the
    frontend can constrain the date picker instead of letting a user
    guess and hit a raw error.
    """
    times, _ = _fetch_daily(lat, lon)
    return times[0], times[-1]


def fetch_live_rain_72h(lat: float, lon: float, target_date: str) -> float:
    """Real live/forecast 72h rainfall (mm) for one point, from Open-Meteo's
    free forecast API - no key required. Used for "what if I pick today"
    risk checks, where the IMD RF25 historical NetCDF (fixed to the 2018
    Titli event) has no data. 92 days back / 16 days forward is Open-Meteo's
    own maximum for this endpoint; outside that window this raises, and the
    caller must disclose that rather than fabricate a number.
    """
    times, precip = _fetch_daily(lat, lon)
    if target_date not in times:
        raise ValueError(
            f"{target_date} is outside the available window "
            f"({times[0]} to {times[-1]})"
        )
    idx = times.index(target_date)
    window = precip[max(0, idx - 2): idx + 1]
    return float(sum(v for v in window if v is not None))


def today_iso() -> str:
    return date_cls.today().isoformat()


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
