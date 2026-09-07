import math

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, Point

from risk.terrain import (
    _slope_from_array, aspect_components, build_grid, compute_flow_accumulation, compute_hand,
    compute_slope, compute_stream_distance, compute_twi, curvature, dist_to_stream, ls_factor,
)


def _write_synthetic_dem(path, dem: np.ndarray, px_size_deg: float = 0.001,
                          origin_lon: float = 92.9, origin_lat: float = 23.85,
                          nodata: float = -9999.0):
    transform = from_origin(origin_lon, origin_lat, px_size_deg, px_size_deg)
    with rasterio.open(
        path, "w", driver="GTiff", height=dem.shape[0], width=dem.shape[1],
        count=1, dtype=dem.dtype, crs="EPSG:4326", transform=transform, nodata=nodata,
    ) as dst:
        dst.write(dem, 1)


def test_flat_dem_has_zero_slope():
    dem = np.zeros((5, 5))
    slope = _slope_from_array(dem, px_size_x_m=30.0, px_size_y_m=30.0)
    assert np.allclose(slope, 0.0)


def test_uniform_ramp_matches_arctan_of_rise_over_run():
    # each column step rises 10m, pixel spacing is 100m -> slope = arctan(10/100)
    rise_per_col = 10.0
    cellsize_m = 100.0
    dem = np.array([[j * rise_per_col for j in range(5)] for _ in range(5)], dtype=float)

    slope = _slope_from_array(dem, px_size_x_m=cellsize_m, px_size_y_m=cellsize_m)

    expected_deg = math.degrees(math.atan(rise_per_col / cellsize_m))
    assert np.allclose(slope, expected_deg, atol=1e-6)


def test_steeper_ramp_gives_larger_slope():
    cellsize_m = 100.0
    gentle = np.array([[j * 5.0 for j in range(5)] for _ in range(5)], dtype=float)
    steep = np.array([[j * 50.0 for j in range(5)] for _ in range(5)], dtype=float)

    gentle_slope = _slope_from_array(gentle, px_size_x_m=cellsize_m, px_size_y_m=cellsize_m)
    steep_slope = _slope_from_array(steep, px_size_x_m=cellsize_m, px_size_y_m=cellsize_m)

    assert steep_slope[2, 2] > gentle_slope[2, 2]


def test_compute_slope_reads_a_real_geotiff_and_converts_degree_pixels_to_meters(tmp_path):
    dem_path = tmp_path / "flat.tif"
    _write_synthetic_dem(dem_path, np.full((10, 10), 5.0, dtype="float32"))

    slope = compute_slope(str(dem_path))

    assert slope.shape == (10, 10)
    assert np.allclose(slope, 0.0, atol=1e-4)


def test_compute_hand_is_zero_at_the_stream_and_nonnegative_elsewhere(tmp_path):
    # a tilted plane: elevation decreases with row index, so every
    # column drains straight down toward the last row (the outlet)
    size = 12
    dem = np.array([[float(size - i) for _ in range(size)] for i in range(size)], dtype="float32")
    dem_path = tmp_path / "valley.tif"
    _write_synthetic_dem(dem_path, dem)

    # accumulation grows linearly with row index (see spike: row k has
    # accumulation k+1) - threshold of 10 makes the last 2 rows "stream".
    # D8 flow direction is undefined at raster edges, so the outermost
    # border comes back NaN - that's real pysheds behaviour, not a bug.
    hand = compute_hand(str(dem_path), stream_accumulation_threshold=10.0)

    assert hand.shape == (size, size)
    valid = ~np.isnan(hand)
    assert valid.any()
    assert np.all(hand[valid] >= -1e-6)
    # row 10 (second-to-last, first stream row that isn't itself a
    # border cell) sits on the stream: HAND is ~0 across its interior
    assert np.allclose(hand[10, 1:-1], 0.0, atol=1e-6)


def test_compute_twi_is_finite_and_increases_downslope_with_accumulation(tmp_path):
    # same tilted plane: constant slope everywhere, accumulation grows
    # with row index -> TWI = ln(upslope_area / tan(slope)) must grow
    # monotonically down each column since only the numerator changes
    size = 12
    dem = np.array([[float(size - i) for _ in range(size)] for i in range(size)], dtype="float32")
    dem_path = tmp_path / "ramp.tif"
    _write_synthetic_dem(dem_path, dem)

    twi = compute_twi(str(dem_path))

    assert twi.shape == (size, size)
    interior_col = twi[1:-1, 5]
    assert np.all(np.isfinite(interior_col))
    assert np.all(np.diff(interior_col) > 0)  # strictly increasing downslope


def test_compute_stream_distance_is_zero_on_stream_cells_and_grows_away_from_them(tmp_path):
    size = 12
    dem = np.array([[float(size - i) for _ in range(size)] for i in range(size)], dtype="float32")
    dem_path = tmp_path / "valley.tif"
    _write_synthetic_dem(dem_path, dem)

    dist = compute_stream_distance(str(dem_path), stream_accumulation_threshold=10.0)

    assert dist.shape == (size, size)
    assert np.all(dist[~np.isnan(dist)] >= 0.0)
    # row 10 is the interior stream row (see the HAND test above) -
    # distance there should be ~0, and further rows away should be larger
    assert np.allclose(dist[10, 1:-1], 0.0, atol=1e-6)
    assert dist[5, 5] > dist[9, 5]


def test_build_grid_covers_the_bbox_at_the_requested_resolution():
    # a small bbox around Aizawl town, ~2.2km x 2.2km at 250m cells
    # -> expect roughly a 9x9 grid (some slop from degree/meter rounding)
    west, south, east, north = 92.89, 23.89, 92.91, 23.91
    grid = build_grid((west, south, east, north), cell_m=250)

    assert isinstance(grid, gpd.GeoDataFrame)
    assert len(grid) > 0
    total_bounds = grid.total_bounds  # (minx, miny, maxx, maxy)
    assert total_bounds[0] <= west + 1e-6
    assert total_bounds[1] <= south + 1e-6
    assert total_bounds[2] >= east - 1e-6
    assert total_bounds[3] >= north - 1e-6
    assert "centroid" in grid.columns
    assert grid.crs is not None


def test_dist_to_stream_is_zero_on_the_line_and_positive_away_from_it():
    waterway = gpd.GeoDataFrame(
        {"geometry": [LineString([(92.90, 23.80), (92.90, 24.00)])]}, crs="EPSG:4326",
    )
    grid = gpd.GeoDataFrame(
        {"geometry": [Point(92.90, 23.90), Point(92.95, 23.90)]}, crs="EPSG:4326",
    )

    distances = dist_to_stream(grid, waterway)

    assert distances[0] == pytest.approx(0.0, abs=1.0)  # on the line
    assert distances[1] > 1000.0  # roughly 5km east of it


def test_dist_to_stream_returns_nan_when_no_waterways_present():
    grid = gpd.GeoDataFrame({"geometry": [Point(92.90, 23.90)]}, crs="EPSG:4326")
    empty_waterways = gpd.GeoDataFrame({"geometry": []}, crs="EPSG:4326")

    distances = dist_to_stream(grid, empty_waterways)

    assert np.isnan(distances[0])


def test_aspect_components_are_a_unit_vector_everywhere(tmp_path):
    size = 10
    # a ramp, not flat, so aspect is well-defined at every interior cell
    dem = np.array([[float(j) for j in range(size)] for _ in range(size)], dtype="float32")
    dem_path = tmp_path / "ramp.tif"
    _write_synthetic_dem(dem_path, dem)

    aspect_sin, aspect_cos = aspect_components(str(dem_path))

    assert aspect_sin.shape == (size, size)
    assert aspect_cos.shape == (size, size)
    magnitude = aspect_sin ** 2 + aspect_cos ** 2
    assert np.allclose(magnitude, 1.0, atol=1e-6)


def test_curvature_is_near_zero_on_a_perfectly_planar_ramp(tmp_path):
    # a linear ramp has zero second derivative everywhere -> both
    # curvatures should be ~0 in the interior (edges use one-sided
    # finite differences and are noisier, so check the interior only)
    size = 12
    dem = np.array([[float(i + j) for j in range(size)] for i in range(size)], dtype="float32")
    dem_path = tmp_path / "planar.tif"
    _write_synthetic_dem(dem_path, dem)

    plan, profile = curvature(str(dem_path))

    assert plan.shape == (size, size)
    assert profile.shape == (size, size)
    interior_plan = plan[2:-2, 2:-2]
    interior_profile = profile[2:-2, 2:-2]
    assert np.allclose(interior_plan[~np.isnan(interior_plan)], 0.0, atol=1e-3)
    assert np.allclose(interior_profile[~np.isnan(interior_profile)], 0.0, atol=1e-3)


def test_curvature_is_nan_on_perfectly_flat_terrain(tmp_path):
    # p (squared gradient magnitude) is exactly 0 everywhere on a flat
    # DEM - curvature is undefined there, not zero, and must say so
    dem = np.zeros((10, 10), dtype="float32")
    dem_path = tmp_path / "flat.tif"
    _write_synthetic_dem(dem_path, dem)

    plan, profile = curvature(str(dem_path))

    assert np.all(np.isnan(plan))
    assert np.all(np.isnan(profile))


def test_ls_factor_increases_with_slope_and_flow_accumulation():
    slope_deg = np.array([5.0, 5.0, 30.0])
    flow_acc = np.array([10.0, 1000.0, 1000.0])

    ls = ls_factor(slope_deg, flow_acc, cell_size_m=30.0)

    assert ls.shape == (3,)
    assert ls[1] > ls[0]  # more upslope accumulation -> higher LS at the same slope
    assert ls[2] > ls[1]  # steeper slope, same accumulation -> higher LS


def test_compute_flow_accumulation_is_at_least_one_everywhere(tmp_path):
    size = 12
    dem = np.array([[float(size - i) for _ in range(size)] for i in range(size)], dtype="float32")
    dem_path = tmp_path / "valley.tif"
    _write_synthetic_dem(dem_path, dem)

    acc = compute_flow_accumulation(str(dem_path))

    assert acc.shape == (size, size)
    assert np.all(acc >= 1.0)  # every cell accumulates at least itself
    assert acc[-1, 1:-1].mean() > acc[0, 1:-1].mean()  # outlet row accumulates more than the source row
