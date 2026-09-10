"""Road isolation analysis: blockage-aware connected components and settlement
isolation scoring.

When a road segment is blocked, it's removed from the graph and connected
components are recomputed. For each settlement: component size, population,
and whether a path to the district headquarters survives. No path to HQ
means an isolation score of 1.0.

Blockage has three sources (predicted, reported, confirmed) and the source
is shown. This module provides the DB-backed implementation with Realtime
broadcast for the isolation view.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
from shapely.geometry import LineString, Point
from supabase import Client, create_client

from config import REGION

_API_DIR = Path(__file__).resolve().parents[1]

_supabase: Client | None = None
_isolation_cache: tuple[float, list[dict[str, Any]]] | None = None
_ISOLATION_CACHE_TTL_S = 15.0


def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(
            "https://bsftkkpdtsqcblnmwbfd.supabase.co",
            "sb_publishable_urAbb_UvLdvF2ORY5PC6_w_XZGT9-7O",
        )
    return _supabase


def fetch_settlement_isolation_scores() -> list[dict[str, Any]]:
    """[{geom, isolation_score}, ...], cached for _ISOLATION_CACHE_TTL_S.

    Fetch this ONCE per severity-recompute batch and pass it to
    nearest_isolation_score, never call that per-request in a loop - a
    queue of N open requests doing N live network round-trips each is
    exactly the bug that made request intake take 2+ minutes (same class
    of mistake as the per-cell rainfall NetCDF reopen fixed earlier today).

    Isolation state only changes when a road is blocked or cleared - a
    rare, discrete event, not something that needs a fresh read on every
    GET /requests poll (admin polls every 4s). The TTL means a demo block
    can take up to ~15s to show up in severity scores; routers/roads.py's
    get_isolation() itself is not cached, so the isolation VIEW is always
    live, only this severity input lags slightly.

    Returns [] on any Supabase error rather than raising - severity must
    never fail request intake over a network hiccup.
    """
    global _isolation_cache
    now = time.monotonic()
    if _isolation_cache is not None and now - _isolation_cache[0] < _ISOLATION_CACHE_TTL_S:
        return _isolation_cache[1]
    try:
        result = _get_supabase().table("settlements").select("geom,isolation_score").execute()
    except Exception:
        return _isolation_cache[1] if _isolation_cache is not None else []
    settlements = [s for s in result.data if s.get("geom")]
    _isolation_cache = (now, settlements)
    return settlements


def nearest_isolation_score(lat: float, lon: float, settlements: list[dict[str, Any]] | None = None) -> float:
    """sev_isolation input for dispatch/severity.py: the nearest
    settlement's last-computed isolation_score.

    Reads settlements.isolation_score directly rather than recomputing
    the whole road graph on every severity refresh - that column is
    kept current by routers/roads.py's get_isolation(), which runs on
    every block/clear/isolation-view request, so this is a cheap read
    of an already-fresh value, not a stale cache.

    Pass `settlements` (from fetch_settlement_isolation_scores(), fetched
    once outside any per-request loop) to avoid a Supabase round-trip per
    call. Omitting it fetches fresh every time - fine for a single lookup,
    wrong inside a loop over the whole queue.
    """
    if settlements is None:
        settlements = fetch_settlement_isolation_scores()
    if not settlements:
        return 0.0
    best = min(
        settlements,
        key=lambda s: (s["geom"]["coordinates"][0] - lon) ** 2 + (s["geom"]["coordinates"][1] - lat) ** 2,
    )
    return float(best.get("isolation_score") or 0.0)


@dataclass
class SettlementIsolation:
    """Isolation state for a single settlement."""
    id: int
    name: str
    population: int
    isolated: bool
    isolation_score: float
    component_size: int
    path_to_hq: bool
    updated_at: str
    lon: float | None = None
    lat: float | None = None


@dataclass
class RoadBlockage:
    """Blockage state for a road segment."""
    segment_id: int
    osm_id: int | None
    blocked: bool
    block_reason: str | None  # predicted | reported | confirmed | cleared
    blocked_since: str | None


_NODE_SNAP_DECIMALS = 6  # ~0.11m at this latitude - merges endpoints that are
# the same real-world junction but weren't digitized with bit-identical floats


def _snap(coord: tuple[float, float]) -> tuple[float, float]:
    return (round(coord[0], _NODE_SNAP_DECIMALS), round(coord[1], _NODE_SNAP_DECIMALS))


def build_road_graph(road_segments: list[dict[str, Any]]) -> nx.Graph:
    """Build a NetworkX graph from road segments.

    Each *consecutive vertex pair* along a segment's LineString becomes
    an edge - not just the segment's first and last point. Real T- and
    Y-junctions in OSM commonly land on the *interior* of a longer way,
    not its endpoint (a minor road meeting a trunk road mid-segment
    without splitting it); an endpoint-only graph never sees that
    junction and the district's road network fragments into thousands
    of tiny disconnected pieces (verified against the real roads.geojson:
    3,937 components, largest only 40 nodes - vs. one 260k-node component
    covering 99% of the network once interior vertices are used). That
    fragmentation is what made every settlement, including Aizawl HQ
    itself, come back "isolated, no path to HQ" before any road was even
    blocked.

    Coordinates are snapped to _NODE_SNAP_DECIMALS so vertices that are
    the same real-world point but not bit-identical floats still merge
    into one graph node. Segments are undirected (a blocked road blocks
    travel in both directions).
    """
    G = nx.Graph()

    for seg in road_segments:
        if seg.get("blocked", False):
            continue  # Skip blocked segments

        geom = seg["geom"]
        if not isinstance(geom, LineString):
            continue

        coords = [_snap(c) for c in geom.coords]
        if len(coords) < 2:
            continue

        for a, b in zip(coords, coords[1:]):
            G.add_edge(a, b, segment_id=seg["id"], osm_id=seg.get("osm_id"))

    return G


def compute_connected_components(G: nx.Graph) -> dict[tuple[float, float], int]:
    """Compute connected components and return a mapping from node to component ID.

    Returns: dict mapping (lon, lat) tuples to component IDs
    """
    components = {}
    for comp_id, nodes in enumerate(nx.connected_components(G)):
        for node in nodes:
            components[node] = comp_id
    return components


def compute_settlement_isolation(
    settlements: list[dict[str, Any]],
    road_segments: list[dict[str, Any]],
    hq_location: tuple[float, float] | None = None,
) -> list[SettlementIsolation]:
    """Compute isolation scores for all settlements given current road blockages.

    Args:
        settlements: List of settlement dicts with id, name, geom, population
        road_segments: List of road segment dicts with id, geom, blocked, block_reason
        hq_location: (lat, lon) of district headquarters. If None, uses REGION center.

    Returns:
        List of SettlementIsolation objects
    """
    if hq_location is None:
        # Use region center as fallback
        bbox = REGION["bbox"]
        hq_location = ((bbox["north"] + bbox["south"]) / 2, (bbox["east"] + bbox["west"]) / 2)

    # Build graph excluding blocked segments
    G = build_road_graph(road_segments)

    # Compute connected components
    node_to_comp = compute_connected_components(G)

    # Find which component contains HQ
    hq_lon, hq_lat = hq_location[1], hq_location[0]
    hq_comp = None

    # Find nearest road node to HQ
    min_dist = float("inf")
    hq_node = None
    for node in G.nodes():
        dist = (node[0] - hq_lon) ** 2 + (node[1] - hq_lat) ** 2
        if dist < min_dist:
            min_dist = dist
            hq_node = node

    if hq_node is not None:
        hq_comp = node_to_comp.get(hq_node)

    # Compute isolation for each settlement
    results = []
    for settlement in settlements:
        geom = settlement["geom"]
        if not isinstance(geom, Point):
            continue

        # Find nearest road node to settlement
        set_lon, set_lat = geom.x, geom.y
        min_dist = float("inf")
        set_node = None
        for node in G.nodes():
            dist = (node[0] - set_lon) ** 2 + (node[1] - set_lat) ** 2
            if dist < min_dist:
                min_dist = dist
                set_node = node

        if set_node is None:
            # Settlement not connected to road network at all
            isolated = True
            isolation_score = 1.0
            component_size = 1
            path_to_hq = False
        else:
            set_comp = node_to_comp.get(set_node)
            component_size = sum(1 for comp in node_to_comp.values() if comp == set_comp)

            # Check if settlement can reach HQ
            path_to_hq = (set_comp is not None) and (set_comp == hq_comp)

            # Isolation logic:
            # - If no path to HQ: isolated = True, score = 1.0
            # - If path to HQ but component is small (< 5 settlements): isolated = True, score = 0.7
            # - Otherwise: isolated = False, score = 0.0
            if not path_to_hq:
                isolated = True
                isolation_score = 1.0
            elif component_size < 5:
                isolated = True
                isolation_score = 0.7
            else:
                isolated = False
                isolation_score = 0.0

        results.append(SettlementIsolation(
            id=settlement["id"],
            name=settlement.get("name", "Unknown"),
            population=settlement.get("population", 0),
            isolated=isolated,
            isolation_score=isolation_score,
            component_size=component_size,
            path_to_hq=path_to_hq,
            updated_at=settlement.get("updated_at", ""),
            lon=geom.x,
            lat=geom.y,
        ))

    return results


def block_road_segment(
    segment_id: int,
    block_reason: str,  # predicted | reported | confirmed
    road_segments: list[dict[str, Any]],
) -> RoadBlockage:
    """Mark a road segment as blocked.

    This updates the segment's blocked status and reason. The actual
    DB update should happen via the router, this function just
    returns the updated state.
    """
    for seg in road_segments:
        if seg["id"] == segment_id:
            seg["blocked"] = True
            seg["block_reason"] = block_reason
            return RoadBlockage(
                segment_id=seg["id"],
                osm_id=seg.get("osm_id"),
                blocked=True,
                block_reason=block_reason,
                blocked_since=seg.get("blocked_since"),
            )

    raise ValueError(f"Road segment {segment_id} not found")


def clear_road_segment(
    segment_id: int,
    road_segments: list[dict[str, Any]],
) -> RoadBlockage:
    """Mark a road segment as cleared (unblocked).

    This updates the segment's blocked status to False and reason to 'cleared'.
    """
    for seg in road_segments:
        if seg["id"] == segment_id:
            seg["blocked"] = False
            seg["block_reason"] = "cleared"
            return RoadBlockage(
                segment_id=seg["id"],
                osm_id=seg.get("osm_id"),
                blocked=False,
                block_reason="cleared",
                blocked_since=None,
            )

    raise ValueError(f"Road segment {segment_id} not found")


def get_demo_trigger_segments() -> list[int]:
    """Return the OSM way IDs for the demo isolation trigger.

    This is the NH6 segment that isolates Lenchim, Tawizo, and Mualpheng.
    See config.py for the full trigger definition.
    """
    from config import DEMO_ROAD_BLOCK_TRIGGER
    return [DEMO_ROAD_BLOCK_TRIGGER["way_id"]]


def get_isolated_settlement_names_for_trigger(way_id: int) -> list[str]:
    """Return the settlement names that become isolated when a given way is blocked.

    This is a simplified version for the demo - in production this would
    be computed dynamically by running the isolation analysis.
    """
    from config import DEMO_ROAD_BLOCK_TRIGGER

    if way_id == DEMO_ROAD_BLOCK_TRIGGER["way_id"]:
        return DEMO_ROAD_BLOCK_TRIGGER["isolated_settlements"]
    elif way_id == DEMO_ROAD_BLOCK_TRIGGER.get("backup_way_id"):
        return DEMO_ROAD_BLOCK_TRIGGER["isolated_settlements"]
    else:
        return []
