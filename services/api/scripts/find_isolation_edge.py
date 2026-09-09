"""Exploratory brute-force: which single road, if blocked, isolates the
most settlements from Aizawl HQ on the real road graph?

This is NOT roads/isolation.py (the production module per BUILD_SPEC.md
#4 - DB-backed, recomputed on every road status change, broadcast via
Realtime). It answers one narrower question first: does a real edge in
this graph exist whose removal disconnects 2+ settlements from HQ, so
the demo's deterministic road-block trigger can be hardcoded against a
verified segment rather than discovered during rehearsal.

Method: build an undirected graph from roads.geojson's LineString
vertices (nodes snapped by rounding to ~0.1m so shared OSM vertices at
intersections merge into one graph node). Snap each settlement and HQ
to the nearest graph node within a generous tolerance. For each OSM way
(one blockable "road segment" in the DB sense - schema.sql's
road_segments.id is one way, not one vertex-to-vertex edge), remove all
its edges, recompute connected components (scipy.sparse.csgraph, not
pure-Python BFS - the raw vertex graph has ~10^5 edges and 4600+ ways
to test, which a per-way Python BFS does not finish in reasonable time),
and count settlements that fall outside HQ's component. Restore the
way, move to the next.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from config import REGION
from ingest.config import DATA_RAW_DIR

ROADS_PATH = DATA_RAW_DIR / "roads.geojson"
SETTLEMENTS_PATH = DATA_RAW_DIR / "settlements.geojson"

SNAP_DECIMALS = 6  # ~0.11m at this latitude - merges shared OSM vertices
SETTLEMENT_SNAP_MAX_M = 1500.0  # settlement centroid to nearest road node
HQ_SNAP_MAX_M = 1500.0

_METERS_PER_DEG_LAT = 111_320.0


def _meters_vec(lon1: float, lat1: float, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    mean_lat = np.radians((lat1 + lats) / 2.0)
    dx = (lons - lon1) * _METERS_PER_DEG_LAT * np.cos(mean_lat)
    dy = (lats - lat1) * _METERS_PER_DEG_LAT
    return np.hypot(dx, dy)


def _snap(lon: float, lat: float) -> tuple[float, float]:
    return (round(lon, SNAP_DECIMALS), round(lat, SNAP_DECIMALS))


def load_graph():
    with open(ROADS_PATH, encoding="utf-8") as f:
        roads = json.load(f)

    node_index: dict[tuple, int] = {}
    node_coords: list[tuple[float, float]] = []

    def node_id(pt: tuple[float, float]) -> int:
        if pt not in node_index:
            node_index[pt] = len(node_coords)
            node_coords.append(pt)
        return node_index[pt]

    eu: list[int] = []
    ev: list[int] = []
    e_way: list[str] = []
    way_props: dict[str, dict] = {}

    for feature in roads["features"]:
        geom = feature["geometry"]
        props = feature["properties"]
        way_id = props.get("@id", f"way/unknown-{id(feature)}")
        way_props[way_id] = props

        if geom["type"] == "LineString":
            coord_lists = [geom["coordinates"]]
        elif geom["type"] == "MultiLineString":
            coord_lists = geom["coordinates"]
        else:
            continue

        for coords in coord_lists:
            nodes = [node_id(_snap(lon, lat)) for lon, lat in coords]
            for a, b in zip(nodes, nodes[1:]):
                if a == b:
                    continue
                eu.append(a)
                ev.append(b)
                e_way.append(way_id)

    eu = np.array(eu, dtype=np.int64)
    ev = np.array(ev, dtype=np.int64)
    e_way = np.array(e_way, dtype=object)
    coords = np.array(node_coords, dtype=np.float64)  # columns: lon, lat

    way_edge_idx: dict[str, np.ndarray] = defaultdict(list)
    for i, w in enumerate(e_way):
        way_edge_idx[w].append(i)
    way_edge_idx = {w: np.array(idxs, dtype=np.int64) for w, idxs in way_edge_idx.items()}

    return coords, eu, ev, way_edge_idx, way_props


def _nearest_node(coords: np.ndarray, lon: float, lat: float, max_m: float) -> int | None:
    dists = _meters_vec(lon, lat, coords[:, 0], coords[:, 1])
    idx = int(np.argmin(dists))
    if dists[idx] > max_m:
        return None
    return idx


def load_settlements() -> list[dict]:
    with open(SETTLEMENTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for feature in data["features"]:
        lon, lat = feature["geometry"]["coordinates"]
        out.append({
            "name": feature["properties"].get("name") or "(unnamed)",
            "place": feature["properties"].get("place"),
            "population": feature["properties"].get("population"),
            "lon": lon,
            "lat": lat,
        })
    return out


def _components(n_nodes: int, eu: np.ndarray, ev: np.ndarray) -> np.ndarray:
    data = np.ones(len(eu), dtype=np.int8)
    matrix = coo_matrix((np.concatenate([data, data]), (np.concatenate([eu, ev]), np.concatenate([ev, eu]))),
                         shape=(n_nodes, n_nodes))
    _, labels = connected_components(matrix, directed=False)
    return labels


def main() -> None:
    print("[isolation] loading road graph from roads.geojson")
    coords, eu, ev, way_edge_idx, way_props = load_graph()
    n_nodes = len(coords)
    print(f"[isolation] graph: {n_nodes} nodes, {len(eu)} edges, {len(way_edge_idx)} distinct ways")

    settlements = load_settlements()
    print(f"[isolation] {len(settlements)} settlements loaded")

    hq_lat, hq_lon = REGION["hq"]
    hq_idx = _nearest_node(coords, hq_lon, hq_lat, HQ_SNAP_MAX_M)
    if hq_idx is None:
        print(f"[isolation] HQ {REGION['hq']} did not snap to any road node within {HQ_SNAP_MAX_M}m - stopping")
        return
    print(f"[isolation] HQ snapped to road node {tuple(coords[hq_idx])}")

    snapped = []
    for s in settlements:
        idx = _nearest_node(coords, s["lon"], s["lat"], SETTLEMENT_SNAP_MAX_M)
        if idx is None:
            print(f"[isolation]   {s['name']!r} did not snap within {SETTLEMENT_SNAP_MAX_M}m - excluded")
            continue
        snapped.append({**s, "node": idx})
    print(f"[isolation] {len(snapped)}/{len(settlements)} settlements snapped to the road graph")

    baseline_labels = _components(n_nodes, eu, ev)
    hq_label = baseline_labels[hq_idx]
    baseline_reachable = [s for s in snapped if baseline_labels[s["node"]] == hq_label]
    print(f"[isolation] baseline: {len(baseline_reachable)}/{len(snapped)} settlements have a path to HQ "
          f"before any blockage")
    if len(baseline_reachable) < len(snapped):
        unreachable = [s["name"] for s in snapped if baseline_labels[s["node"]] != hq_label]
        print(f"[isolation]   already unreachable at baseline (graph gap, not a blockage): {unreachable}")

    print(f"[isolation] brute-forcing {len(way_edge_idx)} ways (removing each in turn, recomputing HQ component)")
    all_idx = np.arange(len(eu))
    results = []
    for way_id, remove_idx in way_edge_idx.items():
        mask = np.ones(len(eu), dtype=bool)
        mask[remove_idx] = False
        labels = _components(n_nodes, eu[mask], ev[mask])
        hq_lbl = labels[hq_idx]
        newly_isolated = [s for s in baseline_reachable if labels[s["node"]] != hq_lbl]
        if newly_isolated:
            first_edge = remove_idx[0]
            results.append({
                "way_id": way_id,
                "highway": way_props[way_id].get("highway"),
                "name": way_props[way_id].get("name"),
                "n_isolated": len(newly_isolated),
                "settlements": [s["name"] for s in newly_isolated],
                "sample_coord": tuple(coords[eu[first_edge]]),
            })

    results.sort(key=lambda r: r["n_isolated"], reverse=True)

    print()
    print(f"[isolation] {len(results)} ways isolate at least one settlement when blocked alone")
    print("[isolation] top 5:")
    for r in results[:5]:
        osm_url = f"https://www.openstreetmap.org/{r['way_id']}"
        print(f"  {r['way_id']}  highway={r['highway']}  name={r['name']!r}  "
              f"isolates {r['n_isolated']}: {r['settlements']}  ({osm_url})  "
              f"near lon,lat={r['sample_coord']}")

    if not results or results[0]["n_isolated"] < 2:
        print()
        print("[isolation] no single way isolates 2+ settlements - a single-edge demo trigger is not "
              "supported by this graph. Fallback: a two-edge blockage is needed; rerun with pair "
              "brute-force if this result holds.")


if __name__ == "__main__":
    main()
