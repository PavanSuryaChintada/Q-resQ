import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point

from ml.sampling import label_positives, sample_negatives, spatial_blocks


def _synthetic_features(n_per_side: int = 20) -> pd.DataFrame:
    # small grid inside the real Aizawl bbox, spaced ~110m apart so it's
    # fine enough to actually land inside a 100m landslide buffer
    lats = np.linspace(23.700, 23.702, n_per_side)
    lons = np.linspace(92.750, 92.752, n_per_side)
    lat_grid, lon_grid = np.meshgrid(lats, lons)
    n = n_per_side * n_per_side
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "lat": lat_grid.ravel(),
        "lon": lon_grid.ravel(),
        "slope_deg": rng.uniform(0, 40, n),
        "lithology": np.full(n, np.nan),
    })


def test_label_positives_marks_only_cells_near_a_landslide_point():
    features = _synthetic_features()
    # one landslide point at the middle of the synthetic grid
    landslides = gpd.GeoDataFrame({"geometry": [Point(92.751, 23.701)]}, crs="EPSG:4326")

    is_positive = label_positives(features, landslides=landslides)

    assert is_positive.sum() > 0
    assert is_positive.sum() < len(features)  # not everything is positive
    # every positive cell must actually be near the one landslide point
    positive_cells = features.loc[is_positive]
    dist_deg = np.sqrt((positive_cells["lat"] - 23.701) ** 2 + (positive_cells["lon"] - 92.751) ** 2)
    assert dist_deg.max() < 0.002  # well under 100m + one grid cell of slack at this grid spacing


def test_label_positives_is_empty_when_no_landslides_are_nearby():
    features = _synthetic_features()
    landslides = gpd.GeoDataFrame({"geometry": [Point(0.0, 0.0)]}, crs="EPSG:4326")  # nowhere near the grid

    is_positive = label_positives(features, landslides=landslides)

    assert is_positive.sum() == 0


def test_sample_negatives_respects_slope_threshold_and_exclusion_zone():
    features = _synthetic_features()
    landslides = gpd.GeoDataFrame({"geometry": [Point(92.751, 23.701)]}, crs="EPSG:4326")
    is_positive = label_positives(features, landslides=landslides)

    is_negative = sample_negatives(features, is_positive, seed=1)

    assert (is_positive & is_negative).sum() == 0  # disjoint from positives
    negative_rows = features.loc[is_negative]
    assert (negative_rows["slope_deg"] > 15.0).all()
    # ratio respected when enough candidates exist
    assert is_negative.sum() <= is_positive.sum() * 3


def test_spatial_blocks_never_splits_a_block_across_folds():
    features = _synthetic_features()

    block_id, fold = spatial_blocks(features, block_km=5.0, n_folds=5, seed=0)

    per_block_folds = pd.DataFrame({"block_id": block_id, "fold": fold}).groupby("block_id")["fold"].nunique()
    assert (per_block_folds == 1).all()
    assert fold.nunique() <= 5
