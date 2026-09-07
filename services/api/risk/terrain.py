"""DEM -> HAND, slope, TWI, dist_stream. See BUILD_SPEC.md.

Runs once at seed time - slow, cache every intermediate raster.
"""

from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
import rasterio
from pysheds.grid import Grid
from scipy.ndimage import distance_transform_edt
from shapely.geometry import box

_METERS_PER_DEGREE_LAT = 111_320.0
_AIZAWL_UTM_CRS = "EPSG:32646"  # UTM zone 46N - covers Aizawl district, Mizoram


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


def aspect_components(dem_path: str) -> tuple[np.ndarray, np.ndarray]:
    """(sin(aspect), cos(aspect)) - aspect is circular, so it is NEVER
    returned or stored as raw degrees. 359deg and 1deg are one degree
    apart; a model fed the raw value would treat them as maximally
    distant. See docs/TRAINING.md #0 trap 3.

    Aspect convention: compass bearing of steepest downslope direction,
    0=north, 90=east (standard GIS convention, matching gdaldem aspect).
    """
    with rasterio.open(dem_path) as dataset:
        dem = dataset.read(1).astype(float)
        transform = dataset.transform
        mean_lat_deg = (dataset.bounds.top + dataset.bounds.bottom) / 2.0

    meters_per_deg_lon = _METERS_PER_DEGREE_LAT * math.cos(math.radians(mean_lat_deg))
    px_size_x_m = abs(transform.a) * meters_per_deg_lon
    px_size_y_m = abs(transform.e) * _METERS_PER_DEGREE_LAT
    gy, gx = np.gradient(dem, px_size_y_m, px_size_x_m)

    # aspect = atan2(dz/dy, -dz/dx), compass convention (0=north, cw+)
    aspect_rad = np.arctan2(gy, -gx)
    return np.sin(aspect_rad), np.cos(aspect_rad)


def curvature(dem_path: str) -> tuple[np.ndarray, np.ndarray]:
    """(plan_curvature, profile_curvature), Zevenbergen & Thorne (1987).

    Profile curvature is along the slope direction - concave (negative
    here) accelerates flow downslope. Plan curvature is across the
    slope - concave concentrates flow laterally into hollows. Concave
    profile curvature is a strong landslide predictor (docs/TRD.md #3):
    subsurface flow concentrates there, raising pore pressure.
    """
    with rasterio.open(dem_path) as dataset:
        dem = dataset.read(1).astype(float)
        transform = dataset.transform
        mean_lat_deg = (dataset.bounds.top + dataset.bounds.bottom) / 2.0

    meters_per_deg_lon = _METERS_PER_DEGREE_LAT * math.cos(math.radians(mean_lat_deg))
    px_size_x_m = abs(transform.a) * meters_per_deg_lon
    px_size_y_m = abs(transform.e) * _METERS_PER_DEGREE_LAT

    zy, zx = np.gradient(dem, px_size_y_m, px_size_x_m)
    zyy, zyx = np.gradient(zy, px_size_y_m, px_size_x_m)
    zxy, zxx = np.gradient(zx, px_size_y_m, px_size_x_m)
    zxy_avg = (zxy + zyx) / 2.0

    p = zx ** 2 + zy ** 2  # squared gradient magnitude
    p_safe = np.where(p < 1e-9, 1e-9, p)

    profile = -(zxx * zx ** 2 + 2 * zxy_avg * zx * zy + zyy * zy ** 2) / (p_safe * (1 + p) ** 1.5)
    plan = -(zxx * zy ** 2 - 2 * zxy_avg * zx * zy + zyy * zx ** 2) / (p_safe ** 1.5)

    # flat cells (p ~ 0): curvature is undefined, not zero - report as such
    profile = np.where(p < 1e-9, np.nan, profile)
    plan = np.where(p < 1e-9, np.nan, plan)
    return plan, profile


def ls_factor(slope_deg: np.ndarray, flow_accumulation: np.ndarray, cell_size_m: float) -> np.ndarray:
    """LS factor (slope length x steepness), the RUSLE formulation
    (Moore & Burch 1986): longer, steeper slopes accumulate more
    driving force. flow_accumulation is cell count (e.g. from
    grid.accumulation in compute_hand/compute_stream_distance), used
    as a proxy for upslope contributing length.
    """
    slope_rad = np.radians(slope_deg)
    upslope_length_m = np.sqrt(np.maximum(flow_accumulation, 0.0)) * cell_size_m
    slope_factor = np.where(
        slope_deg < 5.0,
        10.8 * np.sin(slope_rad) + 0.03,
        16.8 * np.sin(slope_rad) - 0.50,
    )
    return ((upslope_length_m / 22.13) ** 0.4) * (slope_factor)


def compute_flow_accumulation(dem_path: str) -> np.ndarray:
    """Cell-count flow accumulation from the conditioned DEM - the
    ls_factor input. Same conditioning pipeline as compute_hand and
    compute_stream_distance, exposed standalone since ls_factor needs
    it directly rather than a HAND or distance value derived from it.
    """
    grid = Grid.from_raster(dem_path)
    dem = grid.read_raster(dem_path)

    pit_filled = grid.fill_pits(dem)
    flooded = grid.fill_depressions(pit_filled)
    inflated = grid.resolve_flats(flooded)

    fdir = grid.flowdir(inflated)
    return np.asarray(grid.accumulation(fdir), dtype=float)


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


def compute_stream_distance(dem_path: str, stream_accumulation_threshold: float = 1000.0) -> np.ndarray:
    """Distance in metres to the nearest stream cell, derived straight
    from the DEM's own flow accumulation - no OSM waterway data
    needed. Reuses the same conditioning + accumulation pipeline as
    compute_hand, since both need the same stream definition.
    """
    grid = Grid.from_raster(dem_path)
    dem = grid.read_raster(dem_path)

    pit_filled = grid.fill_pits(dem)
    flooded = grid.fill_depressions(pit_filled)
    inflated = grid.resolve_flats(flooded)

    fdir = grid.flowdir(inflated)
    acc = np.asarray(grid.accumulation(fdir))
    stream_mask = acc > stream_accumulation_threshold

    with rasterio.open(dem_path) as dataset:
        transform = dataset.transform
        mean_lat_deg = (dataset.bounds.top + dataset.bounds.bottom) / 2.0
    meters_per_deg_lon = _METERS_PER_DEGREE_LAT * math.cos(math.radians(mean_lat_deg))
    px_size_x_m = abs(transform.a) * meters_per_deg_lon
    px_size_y_m = abs(transform.e) * _METERS_PER_DEGREE_LAT
    px_size_m = (px_size_x_m + px_size_y_m) / 2.0  # near-square at this scale

    if not stream_mask.any():
        return np.full(stream_mask.shape, np.nan)
    return distance_transform_edt(~stream_mask) * px_size_m


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
    grid["centroid"] = grid.geometry.to_crs(_AIZAWL_UTM_CRS).centroid.to_crs("EPSG:4326")
    return grid


def dist_to_stream(grid: gpd.GeoDataFrame, waterways: gpd.GeoDataFrame,
                    projected_crs: str = _AIZAWL_UTM_CRS) -> np.ndarray:
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
