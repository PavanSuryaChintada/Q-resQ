"""Positive/negative sampling and spatial block assignment for the
susceptibility model. See docs/TRAINING.md #0 (traps 1 and 2) and #3.

Negative sampling's lithology-matching criterion (docs/TRAINING.md #3)
is NOT applied here - lithology isn't available yet (needs the GSI
export, docs/DATA.md Part 2.B). Negatives are sampled on the
slope/distance criteria only until it arrives; this is disclosed in
every printed summary, not silently dropped.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

from config import REGION
from ingest.config import DATA_RAW_DIR
from ml.features import OUTPUT_PATH as FEATURES_PATH, build_features

LANDSLIDES_PATH = DATA_RAW_DIR / "landslides.geojson"
OUTPUT_PATH = Path(__file__).resolve().parent / "artifacts" / "train.parquet"

POSITIVE_BUFFER_M = 100.0
NEGATIVE_SLOPE_MIN_DEG = 15.0
NEGATIVE_EXCLUSION_BUFFER_M = 500.0
NEGATIVE_RATIO = 3
MIN_POSITIVES_FOR_A_LEARNED_MODEL = 150

BLOCK_KM = 5.0
N_FOLDS = 5

_METERS_PER_DEGREE_LAT = 111_320.0


def _meters_to_degrees(meters: float, lat: float) -> tuple[float, float]:
    """(deg_lat, deg_lon) equivalent to `meters` at this latitude."""
    deg_lat = meters / _METERS_PER_DEGREE_LAT
    deg_lon = meters / (_METERS_PER_DEGREE_LAT * np.cos(np.radians(lat)))
    return deg_lat, deg_lon


def label_positives(features: pd.DataFrame | list, landslides: gpd.GeoDataFrame | None = None) -> pd.Series:
    # Convert list of dicts to DataFrame if needed
    if isinstance(features, list):
        features = pd.DataFrame(features)

    if landslides is None:
        if not LANDSLIDES_PATH.exists():
            raise FileNotFoundError(f"{LANDSLIDES_PATH} not found - run ingest/landslides.py first")
        landslides = gpd.read_file(LANDSLIDES_PATH)
    utm = REGION["utm"]

    cell_points = gpd.GeoSeries(
        [Point(lon, lat) for lon, lat in zip(features["lon"], features["lat"])], crs="EPSG:4326",
    )
    # buffer in a real projected CRS (metres), not degrees - degree-space
    # buffering is anisotropic and geopandas warns about exactly this
    landslide_buffers_utm = landslides.geometry.to_crs(utm).buffer(POSITIVE_BUFFER_M)
    combined_utm = landslide_buffers_utm.union_all()
    cell_points_utm = cell_points.to_crs(utm)

    is_positive = cell_points_utm.within(combined_utm) | cell_points_utm.intersects(combined_utm)
    n_strict = int(landslides.get("in_strict_bbox", pd.Series(dtype=bool)).sum()) if "in_strict_bbox" in landslides.columns else None

    print(f"[ml.sampling] {len(landslides)} landslide records available (padded search region)")
    if n_strict is not None:
        print(f"[ml.sampling] of which {n_strict} fall inside the strict {REGION['name']} bbox")
    print(f"[ml.sampling] {int(is_positive.sum())} grid cells marked positive after {POSITIVE_BUFFER_M:.0f}m buffering")

    return pd.Series(is_positive.to_numpy(), index=features.index)


def sample_negatives(features: pd.DataFrame, is_positive: pd.Series, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    utm = REGION["utm"]

    positive_points = gpd.GeoSeries(
        [Point(lon, lat) for lon, lat in zip(features.loc[is_positive, "lon"], features.loc[is_positive, "lat"])],
        crs="EPSG:4326",
    )
    exclusion_zone = (
        positive_points.to_crs(utm).buffer(NEGATIVE_EXCLUSION_BUFFER_M).union_all()
        if len(positive_points) else None
    )

    candidate_mask = (features["slope_deg"] > NEGATIVE_SLOPE_MIN_DEG) & (~is_positive)
    if exclusion_zone is not None:
        candidate_points_utm = gpd.GeoSeries(
            [Point(lon, lat) for lon, lat in zip(features["lon"], features["lat"])], crs="EPSG:4326",
        ).to_crs(utm)
        outside_exclusion = ~candidate_points_utm.intersects(exclusion_zone)
        candidate_mask = candidate_mask & outside_exclusion.to_numpy()

    has_lithology = features["lithology"].notna().any()
    if not has_lithology:
        print("[ml.sampling] lithology not available - negative sampling skips the lithology-match "
              "criterion from docs/TRAINING.md #3 (disclosed, not silently dropped)")

    n_positives = int(is_positive.sum())
    n_negatives_wanted = n_positives * NEGATIVE_RATIO
    candidate_idx = features.index[candidate_mask]
    print(f"[ml.sampling] {len(candidate_idx)} candidate negative cells "
          f"(slope > {NEGATIVE_SLOPE_MIN_DEG} deg, outside {NEGATIVE_EXCLUSION_BUFFER_M:.0f}m of any positive)")

    if len(candidate_idx) < n_negatives_wanted:
        print(f"[ml.sampling] WARNING: only {len(candidate_idx)} candidates available, "
              f"wanted {n_negatives_wanted} ({NEGATIVE_RATIO}:1) - using all candidates")
        chosen = candidate_idx
    else:
        chosen = rng.choice(candidate_idx, size=n_negatives_wanted, replace=False)

    is_negative = pd.Series(False, index=features.index)
    is_negative.loc[chosen] = True
    print(f"[ml.sampling] sampled {int(is_negative.sum())} negatives ({n_positives} positives x {NEGATIVE_RATIO})")
    return is_negative


def spatial_blocks(features: pd.DataFrame, block_km: float = BLOCK_KM, n_folds: int = N_FOLDS,
                    seed: int = 0) -> tuple[pd.Series, pd.Series]:
    """Assign each cell to a ~block_km block, then blocks to folds - a
    block is never split across folds. See docs/TRAINING.md #0 trap 1:
    random k-fold leaks through spatial autocorrelation.
    """
    mean_lat = float(features["lat"].mean())
    block_deg_lat, block_deg_lon = _meters_to_degrees(block_km * 1000, mean_lat)

    bbox = REGION["bbox"]
    block_row = ((features["lat"] - bbox["south"]) / block_deg_lat).astype(int)
    block_col = ((features["lon"] - bbox["west"]) / block_deg_lon).astype(int)
    block_id = block_row.astype(str) + "_" + block_col.astype(str)

    unique_blocks = block_id.unique()
    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(unique_blocks)
    fold_for_block = {block: i % n_folds for i, block in enumerate(shuffled)}
    fold = block_id.map(fold_for_block)

    print(f"[ml.sampling] {len(unique_blocks)} spatial blocks (~{block_km}km) assigned across {n_folds} folds")
    return block_id, fold


def build_training_set(force: bool = False, seed: int = 0) -> pd.DataFrame:
    if OUTPUT_PATH.exists() and not force:
        print(f"[ml.sampling] {OUTPUT_PATH} already exists, loading (use force=True to rebuild)")
        return pd.read_parquet(OUTPUT_PATH)

    features = build_features() if FEATURES_PATH.exists() else build_features(force=True)

    is_positive = label_positives(features)
    n_positives = int(is_positive.sum())

    if n_positives < MIN_POSITIVES_FOR_A_LEARNED_MODEL:
        print(f"[ml.sampling] *** {n_positives} positives is below the {MIN_POSITIVES_FOR_A_LEARNED_MODEL} "
              f"threshold from docs/TRAINING.md #3. Per that doc, this is a call for the user, not this "
              f"session: ship the physical index (docs/TRAINING.md #6) instead of training on this few "
              f"points, or wait for the GSI inventory to arrive and push the count higher. ***")

    is_negative = sample_negatives(features, is_positive, seed=seed)
    labelled_mask = is_positive | is_negative

    block_id, fold = spatial_blocks(features, seed=seed)

    train = features.loc[labelled_mask].copy()
    train["label"] = is_positive.loc[labelled_mask].astype(int)
    train["block_id"] = block_id.loc[labelled_mask]
    train["fold"] = fold.loc[labelled_mask]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    train.to_parquet(OUTPUT_PATH, index=False)
    print(f"[ml.sampling] wrote {len(train)} labelled rows ({n_positives} positive, "
          f"{int(is_negative.sum())} negative) to {OUTPUT_PATH}")
    return train


if __name__ == "__main__":
    build_training_set(force=True)
