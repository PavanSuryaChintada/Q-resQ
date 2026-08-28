"""OSM data via Overpass (through osmnx). Idempotent, retries on 429.

Three outputs: facilities.geojson (hospitals, shelters, etc.),
roads.geojson (drivable network), waterways.geojson (for
dist_to_stream).
"""

from __future__ import annotations

import argparse
import time

import osmnx as ox

from ingest.config import BBOX, DATA_RAW_DIR

# osmnx's default (overpass-api.de and its lz4/z mirrors) is
# unreachable from this network (connection timeout on all three) -
# this mirror was verified reachable and serving real responses
ox.settings.overpass_url = "https://overpass.openstreetmap.fr/api"

FACILITIES_PATH = DATA_RAW_DIR / "facilities.geojson"
ROADS_PATH = DATA_RAW_DIR / "roads.geojson"
WATERWAYS_PATH = DATA_RAW_DIR / "waterways.geojson"

FACILITY_AMENITIES = [
    "hospital", "clinic", "doctors", "school",
    "fire_station", "police", "community_centre", "shelter",
]
WATERWAY_TYPES = ["river", "stream", "canal", "drain", "ditch"]

_MAX_RETRIES = 3
_RETRY_BACKOFF_S = 30


def _with_retry(label: str, fn):
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - Overpass raises various transient errors
            is_last = attempt == _MAX_RETRIES
            print(f"[osm] {label} attempt {attempt}/{_MAX_RETRIES} failed: {exc}")
            if is_last:
                raise
            print(f"[osm] retrying {label} in {_RETRY_BACKOFF_S}s")
            time.sleep(_RETRY_BACKOFF_S)


def fetch_facilities(force: bool = False) -> None:
    if FACILITIES_PATH.exists() and not force:
        print(f"[osm] {FACILITIES_PATH} already exists, skipping (use --force to refetch)")
        return

    print(f"[osm] fetching facilities (amenity in {FACILITY_AMENITIES}, plus emergency=*)")
    tags = {"amenity": FACILITY_AMENITIES, "emergency": True}
    gdf = _with_retry("facilities", lambda: ox.features_from_bbox(bbox=BBOX, tags=tags))
    print(f"[osm] found {len(gdf)} raw facility features")

    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.centroid
    keep = [c for c in ["name", "amenity", "emergency"] if c in gdf.columns]
    gdf = gdf[keep + ["geometry"]]
    gdf.to_file(FACILITIES_PATH, driver="GeoJSON")
    print(f"[osm] wrote {len(gdf)} facilities to {FACILITIES_PATH}")


def fetch_roads(force: bool = False) -> None:
    if ROADS_PATH.exists() and not force:
        print(f"[osm] {ROADS_PATH} already exists, skipping (use --force to refetch)")
        return

    print("[osm] fetching drivable road network")
    graph = _with_retry("roads", lambda: ox.graph_from_bbox(bbox=BBOX, network_type="drive"))
    edges = ox.graph_to_gdfs(graph, nodes=False, edges=True)
    print(f"[osm] found {len(edges)} raw edges")

    edges = edges.reset_index()
    for col in ("highway", "maxspeed"):
        if col in edges.columns:
            edges[col] = edges[col].apply(lambda v: v[0] if isinstance(v, list) else v)
    keep = [c for c in ["u", "v", "highway", "maxspeed", "length"] if c in edges.columns]
    edges = edges[keep + ["geometry"]]
    edges.to_file(ROADS_PATH, driver="GeoJSON")
    print(f"[osm] wrote {len(edges)} road edges to {ROADS_PATH}")


def fetch_waterways(force: bool = False) -> None:
    if WATERWAYS_PATH.exists() and not force:
        print(f"[osm] {WATERWAYS_PATH} already exists, skipping (use --force to refetch)")
        return

    print(f"[osm] fetching waterways (waterway in {WATERWAY_TYPES})")
    tags = {"waterway": WATERWAY_TYPES}
    gdf = _with_retry("waterways", lambda: ox.features_from_bbox(bbox=BBOX, tags=tags))
    print(f"[osm] found {len(gdf)} raw waterway features")

    gdf = gdf.copy()
    keep = [c for c in ["name", "waterway"] if c in gdf.columns]
    gdf = gdf[keep + ["geometry"]]
    gdf.to_file(WATERWAYS_PATH, driver="GeoJSON")
    print(f"[osm] wrote {len(gdf)} waterway features to {WATERWAYS_PATH}")


def fetch(force: bool = False) -> None:
    fetch_facilities(force=force)
    fetch_roads(force=force)
    fetch_waterways(force=force)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    fetch(force=args.force)
