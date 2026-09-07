"""dist_road_m and is_cut_slope from roads.geojson + the DEM grid.

Encodes "unplanned hill cutting" - the anthropogenic landslide driver
named explicitly in the problem statement (docs/TRD.md #3). Requires
data/raw/roads.geojson (services/api/ingest/osm.py) and
data/raw/terrain/slope_deg.tif (services/api/ingest/terrain.py) to
already exist.
"""

from __future__ import annotations

import argparse
import math

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.features
from scipy.ndimage import distance_transform_edt

from ingest.config import DATA_RAW_DIR
from ingest.dem import OUTPUT_PATH as DEM_PATH

ROADS_PATH = DATA_RAW_DIR / "roads.geojson"
SLOPE_PATH = DATA_RAW_DIR / "terrain" / "slope_deg.tif"
DIST_ROAD_OUTPUT = DATA_RAW_DIR / "terrain" / "dist_road_m.tif"
IS_CUT_SLOPE_OUTPUT = DATA_RAW_DIR / "terrain" / "is_cut_slope.tif"

CUT_SLOPE_DIST_THRESHOLD_M = 50.0
CUT_SLOPE_SLOPE_THRESHOLD_DEG = 25.0
_METERS_PER_DEGREE_LAT = 111_320.0


def _write_geotiff(path, array: np.ndarray, dtype: str, nodata, reference_dem_path) -> None:
    with rasterio.open(reference_dem_path) as ref:
        profile = ref.profile.copy()
    profile.update(dtype=dtype, count=1, nodata=nodata, driver="GTiff")
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array.astype(dtype), 1)


def derive(force: bool = False) -> None:
    if not ROADS_PATH.exists():
        print(f"[road_cut] {ROADS_PATH} not found - run ingest/osm.py first")
        return
    if not SLOPE_PATH.exists():
        print(f"[road_cut] {SLOPE_PATH} not found - run ingest/terrain.py first")
        return
    if DIST_ROAD_OUTPUT.exists() and IS_CUT_SLOPE_OUTPUT.exists() and not force:
        print(f"[road_cut] {DIST_ROAD_OUTPUT} and {IS_CUT_SLOPE_OUTPUT} already exist, skipping (use --force)")
        return

    with rasterio.open(SLOPE_PATH) as src:
        slope_deg = src.read(1)
        transform = src.transform
        shape = src.shape
        mean_lat = (src.bounds.top + src.bounds.bottom) / 2.0

    print(f"[road_cut] loading {ROADS_PATH}")
    roads = gpd.read_file(ROADS_PATH)
    if len(roads) == 0:
        print("[road_cut] roads.geojson has no features - stopping")
        return

    print(f"[road_cut] rasterizing {len(roads)} road segments onto the DEM grid")
    road_mask = rasterio.features.rasterize(
        [(geom, 1) for geom in roads.geometry if geom is not None],
        out_shape=shape, transform=transform, fill=0, dtype="uint8",
    ).astype(bool)

    if not road_mask.any():
        print("[road_cut] no road geometry overlapped the DEM grid - stopping")
        return

    meters_per_deg_lon = _METERS_PER_DEGREE_LAT * math.cos(math.radians(mean_lat))
    px_size_x_m = abs(transform.a) * meters_per_deg_lon
    px_size_y_m = abs(transform.e) * _METERS_PER_DEGREE_LAT
    px_size_m = (px_size_x_m + px_size_y_m) / 2.0

    print("[road_cut] computing distance to nearest road")
    dist_road_m = distance_transform_edt(~road_mask) * px_size_m
    _write_geotiff(DIST_ROAD_OUTPUT, dist_road_m, "float32", np.nan, DEM_PATH)
    print(f"[road_cut] wrote {DIST_ROAD_OUTPUT}: min={dist_road_m.min():.1f} max={dist_road_m.max():.1f}")

    is_cut_slope = (dist_road_m < CUT_SLOPE_DIST_THRESHOLD_M) & (slope_deg > CUT_SLOPE_SLOPE_THRESHOLD_DEG)
    _write_geotiff(IS_CUT_SLOPE_OUTPUT, is_cut_slope, "uint8", 255, DEM_PATH)

    fraction_flagged = float(is_cut_slope.mean())
    print(f"[road_cut] wrote {IS_CUT_SLOPE_OUTPUT}: {fraction_flagged:.4%} of the district flagged as cut slope")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    derive(force=args.force)
