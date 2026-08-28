import numpy as np
import pandas as pd
import pytest
import xarray as xr

from risk.rainfall import rain_window, rain_window_grid


def _synthetic_dataset():
    times = pd.date_range("2018-10-01", "2018-10-15", freq="D")
    lats = np.array([18.0, 18.25, 18.5])
    lons = np.array([83.5, 83.75, 84.0])
    # every day 0mm except 11 Oct which gets a uniform 80mm spike
    data = np.zeros((len(times), len(lats), len(lons)), dtype="float32")
    data[list(times).index(pd.Timestamp("2018-10-11"))] = 80.0
    return xr.Dataset(
        {"RAINFALL": (("TIME", "LATITUDE", "LONGITUDE"), data)},
        coords={"TIME": times, "LATITUDE": lats, "LONGITUDE": lons},
    )


def test_rain_window_sums_the_trailing_days_inclusive():
    ds = _synthetic_dataset()

    # 72h window ending 2018-10-11 covers 10-09, 10-10, 10-11 -> just the spike day
    total = rain_window(ds, lat=18.25, lon=83.75, end_date="2018-10-11", days=3)

    assert total == pytest.approx(80.0)


def test_rain_window_excludes_days_outside_the_range():
    ds = _synthetic_dataset()

    # window ending 2018-10-09 (before the spike) should be zero
    total = rain_window(ds, lat=18.25, lon=83.75, end_date="2018-10-09", days=3)

    assert total == pytest.approx(0.0)


def test_rain_window_grid_matches_scalar_version_for_each_point():
    ds = _synthetic_dataset()
    lats = np.array([18.0, 18.25, 18.5])
    lons = np.array([83.5, 83.75, 84.0])

    grid_totals = rain_window_grid(ds, lats, lons, end_date="2018-10-11", days=3)

    for i, (lat, lon) in enumerate(zip(lats, lons)):
        assert grid_totals[i] == pytest.approx(rain_window(ds, lat, lon, "2018-10-11", 3))
