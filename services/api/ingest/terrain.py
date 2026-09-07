"""Derive terrain features from the fetched Aizawl DEM at the region's
grid resolution (services/api/config.py:REGION["grid_m"]), writing
each as a cached GeoTIFF to data/raw/terrain/. See docs/DATA.md #2 and
docs/TRD.md #3.

Reuses risk/terrain.py's functions - this script is the disk-cached
ingest wrapper around them, not a separate implementation. Flow
accumulation (needed for ls_factor) is the slow part; cache
everything so re-running after a crash doesn't recompute it.
"""

from __future__ import annotations

import argparse

import numpy as np
import rasterio

from ingest.config import DATA_RAW_DIR
from ingest.dem import OUTPUT_PATH as DEM_PATH
from risk.terrain import (
    aspect_components, compute_flow_accumulation, compute_hand, compute_slope,
    compute_stream_distance, compute_twi, curvature, ls_factor,
)

TERRAIN_DIR = DATA_RAW_DIR / "terrain"


def _write_geotiff(path, array: np.ndarray, reference_dem_path) -> None:
    with rasterio.open(reference_dem_path) as ref:
        profile = ref.profile.copy()
    profile.update(dtype="float32", count=1, nodata=np.nan, driver="GTiff")
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array.astype("float32"), 1)


def _pixel_size_m(dem_path) -> float:
    with rasterio.open(dem_path) as ds:
        mean_lat = (ds.bounds.top + ds.bounds.bottom) / 2.0
        meters_per_deg_lon = 111_320.0 * np.cos(np.radians(mean_lat))
        px_x_m = abs(ds.transform.a) * meters_per_deg_lon
        px_y_m = abs(ds.transform.e) * 111_320.0
    return (px_x_m + px_y_m) / 2.0


def derive(force: bool = False) -> None:
    if not DEM_PATH.exists():
        print(f"[terrain] {DEM_PATH} not found - run ingest/dem.py first")
        return

    TERRAIN_DIR.mkdir(parents=True, exist_ok=True)
    dem_path = str(DEM_PATH)

    outputs = {
        "slope_deg.tif": lambda: compute_slope(dem_path),
        "hand_m.tif": lambda: compute_hand(dem_path),
        "twi.tif": lambda: compute_twi(dem_path),
        "dist_stream_m.tif": lambda: compute_stream_distance(dem_path),
    }
    computed: dict[str, np.ndarray] = {}
    for filename, fn in outputs.items():
        out_path = TERRAIN_DIR / filename
        if out_path.exists() and not force:
            print(f"[terrain] {out_path} already exists, skipping (use --force to refetch)")
            with rasterio.open(out_path) as src:
                computed[filename] = src.read(1)
            continue
        print(f"[terrain] computing {filename}")
        array = fn()
        computed[filename] = array
        _write_geotiff(out_path, array, dem_path)
        valid = array[np.isfinite(array)]
        if valid.size:
            print(f"[terrain]   wrote {out_path}: min={valid.min():.3f} max={valid.max():.3f}")

    aspect_sin_path = TERRAIN_DIR / "aspect_sin.tif"
    aspect_cos_path = TERRAIN_DIR / "aspect_cos.tif"
    if aspect_sin_path.exists() and aspect_cos_path.exists() and not force:
        print(f"[terrain] {aspect_sin_path} and {aspect_cos_path} already exist, skipping")
    else:
        print("[terrain] computing aspect_sin, aspect_cos")
        aspect_sin, aspect_cos = aspect_components(dem_path)
        _write_geotiff(aspect_sin_path, aspect_sin, dem_path)
        _write_geotiff(aspect_cos_path, aspect_cos, dem_path)
        print(f"[terrain]   wrote {aspect_sin_path}, {aspect_cos_path}")

    curv_plan_path = TERRAIN_DIR / "curv_plan.tif"
    curv_prof_path = TERRAIN_DIR / "curv_prof.tif"
    if curv_plan_path.exists() and curv_prof_path.exists() and not force:
        print(f"[terrain] {curv_plan_path} and {curv_prof_path} already exist, skipping")
    else:
        print("[terrain] computing curv_plan, curv_prof")
        plan, profile = curvature(dem_path)
        _write_geotiff(curv_plan_path, plan, dem_path)
        _write_geotiff(curv_prof_path, profile, dem_path)
        valid_plan = plan[np.isfinite(plan)]
        valid_prof = profile[np.isfinite(profile)]
        print(f"[terrain]   wrote {curv_plan_path}: min={valid_plan.min():.4f} max={valid_plan.max():.4f}")
        print(f"[terrain]   wrote {curv_prof_path}: min={valid_prof.min():.4f} max={valid_prof.max():.4f}")

    ls_path = TERRAIN_DIR / "ls_factor.tif"
    if ls_path.exists() and not force:
        print(f"[terrain] {ls_path} already exists, skipping")
    else:
        print("[terrain] computing ls_factor (needs flow accumulation - slow)")
        flow_acc = compute_flow_accumulation(dem_path)
        cell_size_m = _pixel_size_m(dem_path)
        ls = ls_factor(computed["slope_deg.tif"], flow_acc, cell_size_m=cell_size_m)
        _write_geotiff(ls_path, ls, dem_path)
        valid_ls = ls[np.isfinite(ls)]
        print(f"[terrain]   wrote {ls_path}: min={valid_ls.min():.3f} max={valid_ls.max():.3f}")

    print("[terrain] done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    derive(force=args.force)
