"""Assemble real risk cells: terrain features from the real Srikakulam
DEM + real IMD rainfall + the heuristic formula. Disk-cached, since
HAND/TWI/stream-distance each take ~80s on the full DEM.

No LightGBM model or SAR labels yet (risk/model.py, risk/labels.py
not built) - this is the heuristic path, labelled as such downstream.
No soil drainage data source in hand either - drainage_penalty
defaults to a neutral 0.5, disclosed here rather than faked as real.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from risk.heuristic import band, compute_heuristic_risk
from risk.rainfall import load_rainfall_dataset, rain_window
from risk.terrain import build_grid, compute_hand, compute_slope, compute_stream_distance, compute_twi

_API_DIR = Path(__file__).resolve().parents[1]
FULL_DEM_PATH = str(_API_DIR / "data" / "raw" / "srikakulam_dem.tif")
DEM_PATH = str(_API_DIR / "data" / "raw" / "srikakulam_dem_demo_crop.tif")
RAINFALL_NC_PATH = "C:/Users/prave/Downloads/RF25_ind2018_rfp25.nc"
CACHE_PATH = _API_DIR / "data" / "raw" / "risk_cells_cache.npy"

# Focused demo area around Srikakulam town/coast - the full-district
# DEM works for HAND/TWI (computed once over the whole raster), but
# the grid itself is kept small so sampling + the map stay fast
DEMO_BBOX = (83.75, 18.20, 84.05, 18.45)
GRID_CELL_M = 250.0
EVENT_END_DATE = "2018-10-11"  # Titli landfall, see docs/PRD.md #5


def _nearest_pixel_values(raster: np.ndarray, transform, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    rows, cols = rasterio.transform.rowcol(transform, lons, lats)
    rows = np.clip(np.asarray(rows), 0, raster.shape[0] - 1)
    cols = np.clip(np.asarray(cols), 0, raster.shape[1] - 1)
    return raster[rows, cols]


def _fill_nan(values: np.ndarray, worst_case: float) -> np.ndarray:
    if np.isnan(values).all():
        return np.full_like(values, worst_case)
    fallback = np.nanmax(values) if np.isfinite(np.nanmax(values)) else worst_case
    return np.nan_to_num(values, nan=fallback)


def _ensure_cropped_dem() -> None:
    """Crop the full-district DEM to the demo bbox once. The demo area
    is ~5% of the district, and this machine has ~7.7GB RAM total -
    running HAND/TWI/stream-distance on the full 3960x2880 raster
    three times in one process reliably OOMs; on the small crop it's
    fast and cheap.
    """
    if Path(DEM_PATH).exists():
        return
    print(f"[features] cropping the full DEM to the demo bbox {DEMO_BBOX}")
    west, south, east, north = DEMO_BBOX
    with rasterio.open(FULL_DEM_PATH) as src:
        window = rasterio.windows.from_bounds(west, south, east, north, src.transform)
        data = src.read(1, window=window)
        transform = src.window_transform(window)
        profile = src.profile.copy()
    profile.update(height=data.shape[0], width=data.shape[1], transform=transform)
    with rasterio.open(DEM_PATH, "w", **profile) as dst:
        dst.write(data, 1)
    print(f"[features] cropped DEM: {data.shape}")


def build_risk_cells(force: bool = False) -> list[dict]:
    if CACHE_PATH.exists() and not force:
        return list(np.load(CACHE_PATH, allow_pickle=True))

    _ensure_cropped_dem()

    print("[features] computing terrain features from the cropped demo-area DEM")
    hand = compute_hand(DEM_PATH)
    slope = compute_slope(DEM_PATH)
    twi = compute_twi(DEM_PATH)
    stream_dist = compute_stream_distance(DEM_PATH)

    with rasterio.open(DEM_PATH) as src:
        transform = src.transform

    print("[features] building the 250m grid over the demo area")
    grid = build_grid(DEMO_BBOX, cell_m=GRID_CELL_M)
    lats = grid["centroid"].y.to_numpy()
    lons = grid["centroid"].x.to_numpy()

    hand_vals = _fill_nan(_nearest_pixel_values(hand, transform, lats, lons), worst_case=0.0)
    slope_vals = _fill_nan(_nearest_pixel_values(slope, transform, lats, lons), worst_case=0.0)
    twi_vals = _nearest_pixel_values(twi, transform, lats, lons)
    stream_vals = _fill_nan(_nearest_pixel_values(stream_dist, transform, lats, lons), worst_case=2000.0)

    print("[features] loading real IMD rainfall for the Titli landfall date")
    rain_ds = load_rainfall_dataset(RAINFALL_NC_PATH)
    rain_vals = np.array([
        rain_window(rain_ds, lat, lon, EVENT_END_DATE, days=3) for lat, lon in zip(lats, lons)
    ])

    drainage_vals = np.full(len(grid), 0.5)  # no soil drainage source yet - neutral default

    risk_score, contributions = compute_heuristic_risk(
        hand_vals, rain_vals, slope_vals, stream_vals, drainage_vals,
    )

    cells = []
    for i in range(len(grid)):
        cells.append({
            "id": i,
            "lat": float(lats[i]),
            "lon": float(lons[i]),
            "hand_m": float(hand_vals[i]),
            "slope_deg": float(slope_vals[i]),
            "twi": float(twi_vals[i]) if np.isfinite(twi_vals[i]) else None,
            "dist_stream_m": float(stream_vals[i]),
            "rain_72h_mm": float(rain_vals[i]),
            "risk_score": float(risk_score[i]),
            "risk_band": band(float(risk_score[i])),
            "contributions": {k: float(v[i]) for k, v in contributions.items()},
        })

    np.save(CACHE_PATH, np.array(cells, dtype=object), allow_pickle=True)
    print(f"[features] computed and cached {len(cells)} risk cells at {CACHE_PATH}")
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
