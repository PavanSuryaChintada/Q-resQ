"""DEM -> HAND, slope, TWI, dist_stream. See BUILD_SPEC.md.

Runs once at seed time - slow, cache every intermediate raster.
"""

from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
import rasterio
from pysheds.grid import Grid
from shapely.geometry import box

_METERS_PER_DEGREE_LAT = 111_320.0
_SRIKAKULAM_UTM_CRS = "EPSG:32644"  # UTM zone 44N - covers Srikakulam district


def _slope_from_array(dem: np.ndarray, px_size_x_m: float, px_size_y_m: float) -> np.ndarray:
    gy, gx = np.gradient(dem, px_size_y_m, px_size_x_m)
    slope_rad = np.arctan(np.sqrt(gx ** 2 + gy ** 2))
    return np.degrees(slope_rad)


def compute_slope(dem_path: str) -> np.ndarray:
    with rasterio.open(dem_path) as dataset:
        dem = dataset.read(1).astype(float)
        transform = dataset.transform
        mean_lat_deg = (dataset.bounds.top + dataset.bounds.bottom) / 2.0

    meters_per_deg_lon = _METERS_PER_DEGREE_LAT * math.cos(math.radians(mean_lat_deg))
    px_size_x_m = abs(transform.a) * meters_per_deg_lon
    px_size_y_m = abs(transform.e) * _METERS_PER_DEGREE_LAT
    return _slope_from_array(dem, px_size_x_m, px_size_y_m)


def compute_hand(dem_path: str, stream_accumulation_threshold: float = 1000.0) -> np.ndarray:
    """Height above nearest drainage. See BUILD_SPEC.md risk/terrain.py.

    fill pits -> fill depressions -> resolve flats (a conditioned DEM
    - skipping this gives HAND values that look plausible and are
    wrong) -> flow direction -> accumulation -> threshold to a stream
    network -> HAND relative to that network.
    """
    grid = Grid.from_raster(dem_path)
    dem = grid.read_raster(dem_path)

    pit_filled = grid.fill_pits(dem)
    flooded = grid.fill_depressions(pit_filled)
    inflated = grid.resolve_flats(flooded)

    fdir = grid.flowdir(inflated)
    acc = grid.accumulation(fdir)
    stream_mask = acc > stream_accumulation_threshold

    hand = grid.compute_hand(fdir, inflated, stream_mask)
    return np.asarray(hand)


def compute_twi(dem_path: str) -> np.ndarray:
    """Topographic wetness index: ln(upslope_area / tan(slope))."""
    grid = Grid.from_raster(dem_path)
    dem = grid.read_raster(dem_path)

    pit_filled = grid.fill_pits(dem)
    flooded = grid.fill_depressions(pit_filled)
    inflated = grid.resolve_flats(flooded)

    fdir = grid.flowdir(inflated)
    upslope_area = np.asarray(grid.accumulation(fdir), dtype=float)

    slope_deg = compute_slope(dem_path)
    tan_slope = np.tan(np.radians(slope_deg))
    tan_slope_safe = np.where(tan_slope < 1e-6, 1e-6, tan_slope)  # flat cells: avoid /0

    return np.log(np.maximum(upslope_area, 1.0) / tan_slope_safe)


def build_grid(bbox: tuple[float, float, float, float], cell_m: float = 250.0) -> gpd.GeoDataFrame:
    """bbox = (west, south, east, north) in degrees (EPSG:4326)."""
    west, south, east, north = bbox
    mean_lat_deg = (south + north) / 2.0
    meters_per_deg_lon = _METERS_PER_DEGREE_LAT * math.cos(math.radians(mean_lat_deg))
    cell_deg_x = cell_m / meters_per_deg_lon
    cell_deg_y = cell_m / _METERS_PER_DEGREE_LAT

    n_cols = max(1, math.ceil((east - west) / cell_deg_x))
    n_rows = max(1, math.ceil((north - south) / cell_deg_y))

    polygons = []
    for row in range(n_rows):
        y0 = south + row * cell_deg_y
        for col in range(n_cols):
            x0 = west + col * cell_deg_x
            polygons.append(box(x0, y0, x0 + cell_deg_x, y0 + cell_deg_y))

    grid = gpd.GeoDataFrame({"geometry": polygons}, crs="EPSG:4326")
    # centroid in a projected CRS, then back to EPSG:4326 for storage -
    # geographic-CRS centroids are imprecise (rasterio/geopandas warns)
    grid["centroid"] = grid.geometry.to_crs(_SRIKAKULAM_UTM_CRS).centroid.to_crs("EPSG:4326")
    return grid


def dist_to_stream(grid: gpd.GeoDataFrame, waterways: gpd.GeoDataFrame,
                    projected_crs: str = _SRIKAKULAM_UTM_CRS) -> np.ndarray:
    """Nearest-neighbour distance in metres from each grid geometry to
    the waterway network. A missing key in the caller's feature matrix
    should treat a NaN result as unreachable-to-stream data, not zero.
    """
    if len(waterways) == 0:
        return np.full(len(grid), np.nan)

    grid_proj = grid.to_crs(projected_crs)
    waterways_proj = waterways.to_crs(projected_crs)
    combined = waterways_proj.geometry.union_all()
    return grid_proj.geometry.distance(combined).to_numpy()
