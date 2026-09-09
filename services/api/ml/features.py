"""Assemble one row per grid cell (REGION["grid_m"] resolution) from
the terrain/landcover rasters ingest/ produced. Static features only -
rainfall is a trigger (trigger.py), not assembled here. See
docs/TRAINING.md #2.

Two columns are honestly null right now, not fabricated:
- lithology: needs the GSI export, not yet available (docs/DATA.md
  Part 2.B, handled outside this ingest session)
- dist_road_m / is_cut_slope: needs roads.geojson, blocked on OSM
  Overpass access (see ingest/osm.py) - ingest/road_cut.py is ready
  to backfill these the moment roads.geojson exists
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

from config import REGION
from ingest.config import DATA_RAW_DIR
from ingest.dem import OUTPUT_PATH as DEM_PATH
from risk.terrain import build_grid

TERRAIN_DIR = DATA_RAW_DIR / "terrain"
LANDCOVER_PATH = DATA_RAW_DIR / "landcover.tif"
FOREST_FRAC_PATH = DATA_RAW_DIR / "forest_frac.tif"
DIST_ROAD_PATH = TERRAIN_DIR / "dist_road_m.tif"
IS_CUT_SLOPE_PATH = TERRAIN_DIR / "is_cut_slope.tif"

OUTPUT_PATH = Path(__file__).resolve().parent / "artifacts" / "features.parquet"

_TERRAIN_RASTERS = {
    "slope_deg": TERRAIN_DIR / "slope_deg.tif",
    "hand_m": TERRAIN_DIR / "hand_m.tif",
    "twi": TERRAIN_DIR / "twi.tif",
    "dist_stream_m": TERRAIN_DIR / "dist_stream_m.tif",
    "aspect_sin": TERRAIN_DIR / "aspect_sin.tif",
    "aspect_cos": TERRAIN_DIR / "aspect_cos.tif",
    "curv_plan": TERRAIN_DIR / "curv_plan.tif",
    "curv_prof": TERRAIN_DIR / "curv_prof.tif",
    "ls_factor": TERRAIN_DIR / "ls_factor.tif",
}


def _nearest_pixel_values(raster_path: Path, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    with rasterio.open(raster_path) as src:
        raster = src.read(1)
        transform = src.transform
    rows, cols = rasterio.transform.rowcol(transform, lons, lats)
    rows = np.clip(np.asarray(rows), 0, raster.shape[0] - 1)
    cols = np.clip(np.asarray(cols), 0, raster.shape[1] - 1)
    return raster[rows, cols]


def build_features(force: bool = False) -> pd.DataFrame:
    if OUTPUT_PATH.exists() and not force:
        print(f"[ml.features] {OUTPUT_PATH} already exists, loading (use force=True to rebuild)")
        return pd.read_parquet(OUTPUT_PATH)

    if not DEM_PATH.exists():
        raise FileNotFoundError(f"{DEM_PATH} not found - run ingest/dem.py first")
    missing_terrain = [name for name, path in _TERRAIN_RASTERS.items() if not path.exists()]
    if missing_terrain:
        raise FileNotFoundError(f"missing terrain rasters {missing_terrain} - run ingest/terrain.py first")

    grid_m = REGION["grid_m"]
    bbox = REGION["bbox"]
    print(f"[ml.features] building the {grid_m}m grid over {REGION['name']}")
    grid = build_grid((bbox["west"], bbox["south"], bbox["east"], bbox["north"]), cell_m=grid_m)
    lats = grid["centroid"].y.to_numpy()
    lons = grid["centroid"].x.to_numpy()
    print(f"[ml.features] {len(lats)} grid cells")

    data: dict[str, np.ndarray] = {"lat": lats, "lon": lons}
    for name, path in _TERRAIN_RASTERS.items():
        data[name] = _nearest_pixel_values(path, lats, lons)

    if LANDCOVER_PATH.exists():
        data["landcover"] = _nearest_pixel_values(LANDCOVER_PATH, lats, lons)
    else:
        print(f"[ml.features] {LANDCOVER_PATH} not found - landcover column will be null")
        data["landcover"] = np.full(len(lats), np.nan)

    if FOREST_FRAC_PATH.exists():
        data["forest_frac"] = _nearest_pixel_values(FOREST_FRAC_PATH, lats, lons)
    else:
        print(f"[ml.features] {FOREST_FRAC_PATH} not found - forest_frac column will be null")
        data["forest_frac"] = np.full(len(lats), np.nan)

    if DIST_ROAD_PATH.exists() and IS_CUT_SLOPE_PATH.exists():
        data["dist_road_m"] = _nearest_pixel_values(DIST_ROAD_PATH, lats, lons)
        data["is_cut_slope"] = _nearest_pixel_values(IS_CUT_SLOPE_PATH, lats, lons).astype(bool)
    else:
        print("[ml.features] dist_road_m/is_cut_slope not available yet (blocked on OSM roads data, "
              "see ingest/road_cut.py) - both columns will be null, NOT fabricated")
        data["dist_road_m"] = np.full(len(lats), np.nan)
        data["is_cut_slope"] = np.full(len(lats), np.nan)

    print("[ml.features] lithology not available yet (needs GSI export, docs/DATA.md Part 2.B) "
          "- column will be null, NOT fabricated")
    data["lithology"] = np.full(len(lats), np.nan)

    df = pd.DataFrame(data)
    df.index.name = "cell_id"
    df = df.reset_index()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)

    print(f"[ml.features] wrote {len(df)} rows to {OUTPUT_PATH}")
    print(f"[ml.features] null counts:\n{df.isna().sum()}")
    cut_frac = df["is_cut_slope"].mean(skipna=True)
    if not np.isnan(cut_frac):
        print(f"[ml.features] {cut_frac:.4%} of cells flagged is_cut_slope")
    return df


if __name__ == "__main__":
    build_features(force=True)
