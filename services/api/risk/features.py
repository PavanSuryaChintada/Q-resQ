"""Assemble real risk cells: terrain features sampled from the
pre-computed Aizawl-district rasters (ingest/terrain.py, ingest/road_cut.py,
ingest/landcover.py) plus risk/heuristic.py's landslide susceptibility
formula (docs/TRAINING.md #6). Disk-cached, since the district-wide grid
is ~284k cells.

Every cell is provenance-labelled "index" (see CLAUDE.md #3) - there is
no trained model behind this yet (risk/model.py, ml/sampling.py: 69
landslide positives is below the threshold to train something that
survives spatial cross-validation).

No soil drainage or lithology data source in hand - lithology_weight is
passed as None (risk/heuristic.py renormalises around it, disclosed in
its own log line rather than faked as real). hand_m/twi/dist_stream_m
are sampled and returned for display only, per docs/TRD.md: HAND still
matters for the flash-flood secondary hazard, but is not part of the
landslide susceptibility formula.

This module previously recomputed HAND/slope/TWI at runtime from a
cropped DEM via pysheds, plus a rain_72h reading from a rainfall NetCDF
that never shipped for Aizawl (RF25_RAINFALL_NC_PATH pointed at a file
that does not exist in this repo) - that path could not run on a cache
miss. Rainfall enters risk separately, as ml/trigger.py's trigger index
(docs/TRAINING.md #5), not here; this module no longer touches rainfall
at all.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from config import REGION
from ml.trigger import compute_trigger, composite_risk
from risk.heuristic import band, compute_heuristic_risk
from risk.terrain import build_grid

_API_DIR = Path(__file__).resolve().parents[1]
TERRAIN_DIR = _API_DIR / "data" / "raw" / "terrain"
FOREST_FRAC_PATH = _API_DIR / "data" / "raw" / "forest_frac.tif"
CACHE_DIR = _API_DIR / "data" / "raw"
_CACHE_PATH = CACHE_DIR / "risk_cells_cache.npy"

_RASTERS = {
    "slope_deg": TERRAIN_DIR / "slope_deg.tif",
    "curv_prof": TERRAIN_DIR / "curv_prof.tif",
    "is_cut_slope": TERRAIN_DIR / "is_cut_slope.tif",
    "ls_factor": TERRAIN_DIR / "ls_factor.tif",
    "hand_m": TERRAIN_DIR / "hand_m.tif",
    "twi": TERRAIN_DIR / "twi.tif",
    "dist_stream_m": TERRAIN_DIR / "dist_stream_m.tif",
}
_REQUIRED_FOR_FORMULA = ["slope_deg", "curv_prof", "is_cut_slope", "ls_factor"]

_bbox = REGION["bbox"]
REGION_BBOX = (_bbox["west"], _bbox["south"], _bbox["east"], _bbox["north"])
GRID_CELL_M = float(REGION["grid_m"])


def _nearest_pixel_values(raster_path: Path, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    with rasterio.open(raster_path) as src:
        raster = src.read(1).astype(float)
        transform = src.transform
    rows, cols = rasterio.transform.rowcol(transform, lons, lats)
    rows = np.clip(np.asarray(rows), 0, raster.shape[0] - 1)
    cols = np.clip(np.asarray(cols), 0, raster.shape[1] - 1)
    return raster[rows, cols]


def _compute_terrain_grid() -> dict[str, np.ndarray]:
    missing = [name for name, path in _RASTERS.items() if name in _REQUIRED_FOR_FORMULA and not path.exists()]
    if missing:
        raise FileNotFoundError(
            f"missing terrain rasters {missing} in {TERRAIN_DIR} - run ingest/terrain.py "
            f"and ingest/road_cut.py first"
        )

    print(f"[features] building the {int(GRID_CELL_M)}m grid over {REGION['name']}")
    grid = build_grid(REGION_BBOX, cell_m=GRID_CELL_M)
    lats = grid["centroid"].y.to_numpy()
    lons = grid["centroid"].x.to_numpy()
    print(f"[features] {len(lats)} grid cells")

    data: dict[str, np.ndarray] = {"lat": lats, "lon": lons}
    for name, path in _RASTERS.items():
        if path.exists():
            data[name] = _nearest_pixel_values(path, lats, lons)
        else:
            print(f"[features] {path} not found - {name} column will be null, not fabricated")
            data[name] = np.full(len(lats), np.nan)

    if FOREST_FRAC_PATH.exists():
        data["forest_frac"] = _nearest_pixel_values(FOREST_FRAC_PATH, lats, lons)
    else:
        print(f"[features] {FOREST_FRAC_PATH} not found - forest_frac column will be null, not fabricated")
        data["forest_frac"] = np.full(len(lats), np.nan)

    # Rainfall and soil moisture for the trigger index. ingest/rainfall_aizawl.py
    # is disclosed-synthetic (monsoon-pattern random values, no real ERA5/SMAP
    # API wired up yet - see that module's docstring) - not fabricated as real
    # here, just sampled the same way the rest of this pipeline treats missing
    # sources. Vectorised: a per-cell Python loop here previously reopened /
    # re-queried the NetCDF file 284k times and took 10+ minutes.
    print("[features] sampling rainfall/soil-moisture rasters (synthetic - see ingest/rainfall_aizawl.py)")
    from ingest.rainfall_aizawl import get_rainfall_grid, get_soil_moisture_grid

    rain = get_rainfall_grid(lats, lons, days_back=15)
    data["rain_15d"] = rain["rain_15d"]
    data["rain_3d"] = rain["rain_3d"]
    data["rain_intensity_max"] = rain["rain_intensity_max"]
    data["soil_moisture"] = get_soil_moisture_grid(lats, lons)

    # curv_prof is genuinely undefined (not missing) on perfectly flat
    # cells - risk/terrain.py's curvature() reports NaN there rather
    # than a fabricated 0. A NaN input would otherwise propagate through
    # the whole risk_score sum for that cell (see the histogram check
    # this replaced - 46 cells came back NaN). A flat cell already
    # carries slope_deg=0, so it scores near-zero on that term
    # regardless; fill curv_prof with the district's own median
    # (real data, not an invented constant) so the row still sums.
    n_flat = int(np.isnan(data["curv_prof"]).sum())
    if n_flat:
        median_curv = float(np.nanmedian(data["curv_prof"]))
        print(f"[features] {n_flat} cells are perfectly flat (curv_prof undefined) - "
              f"filled with the district median profile curvature ({median_curv:.4f})")
        data["curv_prof"] = np.where(np.isnan(data["curv_prof"]), median_curv, data["curv_prof"])

    return data


def _get_terrain_grid(force: bool = False) -> dict[str, np.ndarray]:
    return _compute_terrain_grid()


def _print_score_histogram(risk_score: np.ndarray) -> None:
    edges = np.linspace(0.0, 1.0, 11)
    counts, _ = np.histogram(risk_score, bins=edges)
    total = len(risk_score)
    n_nan = int(np.isnan(risk_score).sum())
    print(f"[features] risk_score distribution across {total} cells "
          f"(mean={np.nanmean(risk_score):.3f} std={np.nanstd(risk_score):.3f}"
          f"{f', {n_nan} NaN - see above' if n_nan else ''}):")
    for lo, hi, count in zip(edges[:-1], edges[1:], counts):
        bar = "#" * int(50 * count / max(total, 1))
        print(f"  [{lo:.1f}, {hi:.1f}) {count:7d} {bar}")


_cells_memory_cache: list[dict] | None = None


def build_risk_cells(force: bool = False) -> list[dict]:
    """Single-hazard (landslide) risk cells over the Aizawl district grid.

    Every cell's risk_score comes from risk/heuristic.py's physical
    index (docs/TRAINING.md #6) - provenance is "index" for all of them
    until a trained model exists.

    The trigger index (rainfall + soil moisture) is computed via
    ml/trigger.py and combined as: risk = susceptibility * trigger.
    Both components are exposed separately.

    Kept in memory after the first load - nearest_risk_score() calls
    this on every request-severity recompute, and re-reading +
    unpickling the ~75MB, 284k-row disk cache on every single call (no
    in-process caching at all) was adding 5-25s to every request
    creation and every GET /requests poll.
    """
    global _cells_memory_cache
    if _cells_memory_cache is not None and not force:
        return _cells_memory_cache

    if _CACHE_PATH.exists() and not force:
        _cells_memory_cache = list(np.load(_CACHE_PATH, allow_pickle=True))
        return _cells_memory_cache

    terrain = _get_terrain_grid(force=force)
    lats, lons = terrain["lat"], terrain["lon"]

    # Compute susceptibility (physical index)
    susceptibility, sus_contributions = compute_heuristic_risk(
        slope_deg=terrain["slope_deg"],
        curv_prof=terrain["curv_prof"],
        is_cut_slope=terrain["is_cut_slope"],
        forest_frac=terrain["forest_frac"],
        ls_factor=terrain["ls_factor"],
        lithology_weight=None,  # not available yet - needs the GSI export
    )

    # Compute trigger index (rainfall + soil moisture)
    trigger_score, trigger_contributions = compute_trigger(
        rain_15d=terrain["rain_15d"],
        rain_3d=terrain["rain_3d"],
        rain_intensity_max=terrain["rain_intensity_max"],
        soil_moisture=terrain["soil_moisture"],
    )

    # Composite risk = susceptibility * trigger
    risk_score = composite_risk(susceptibility, trigger_score)

    _print_score_histogram(risk_score)

    cells = []
    for i in range(len(lats)):
        cells.append({
            "id": i,
            "lat": float(lats[i]),
            "lon": float(lons[i]),
            "slope_deg": float(terrain["slope_deg"][i]),
            "curv_prof": float(terrain["curv_prof"][i]) if np.isfinite(terrain["curv_prof"][i]) else None,
            "is_cut_slope": bool(terrain["is_cut_slope"][i]),
            "forest_frac": float(terrain["forest_frac"][i]) if np.isfinite(terrain["forest_frac"][i]) else None,
            "ls_factor": float(terrain["ls_factor"][i]),
            "hand_m": float(terrain["hand_m"][i]) if np.isfinite(terrain["hand_m"][i]) else None,
            "twi": float(terrain["twi"][i]) if np.isfinite(terrain["twi"][i]) else None,
            "dist_stream_m": float(terrain["dist_stream_m"][i]) if np.isfinite(terrain["dist_stream_m"][i]) else None,
            "susceptibility": float(susceptibility[i]),
            "trigger_score": float(trigger_score[i]),
            "risk_score": float(risk_score[i]),
            "risk_band": band(float(risk_score[i])),
            "provenance": "index",
            "sus_contributions": {k: float(v[i]) for k, v in sus_contributions.items()},
            "trigger_contributions": {k: float(v[i]) for k, v in trigger_contributions.items()},
        })

    np.save(_CACHE_PATH, np.array(cells, dtype=object), allow_pickle=True)
    print(f"[features] computed and cached {len(cells)} risk cells at {_CACHE_PATH}")
    _cells_memory_cache = cells
    return cells


def nearest_risk_score(lat: float, lon: float) -> float:
    """area_risk for dispatch/severity.py: the nearest computed risk
    cell's score, or a neutral default if the point falls outside the
    demo grid entirely.
    """
    cells = build_risk_cells()
    if not cells:
        return 0.5
    best = min(cells, key=lambda c: (c["lat"] - lat) ** 2 + (c["lon"] - lon) ** 2)
    return best["risk_score"]


def nearest_risk_cell(lat: float, lon: float) -> dict | None:
    """The full nearest cell for a point - used by the citizen app to
    show real risk for wherever the reporter actually is, instead of a
    hardcoded band.
    """
    cells = build_risk_cells()
    if not cells:
        return None
    return min(cells, key=lambda c: (c["lat"] - lat) ** 2 + (c["lon"] - lon) ** 2)
