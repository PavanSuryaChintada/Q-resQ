"""Real road-following routes for wheeled units, via the public OSRM
demo routing server.

Every Overpass API mirror this build tried (services/api/ingest/osm.py -
the default host, plus two fallbacks) was unreachable from this network,
so self-hosting a road graph (the docs/BUILD_SPEC.md plan, osmnx +
networkx) was never possible. OSRM's public demo server needs no graph
of our own - it returns real road-snapped geometry directly. It is
explicitly rate-limited and meant for light/prototype use, not
production traffic - fine for a demo, disclosed here rather than
presented as production-grade.

Boats never call this - open water isn't a road-network problem, so
they stay on a direct line between unit and request.
"""

from __future__ import annotations

import json
import urllib.request

ROAD_KINDS = {"ambulance", "truck", "team"}

_OSRM_URL = (
    "https://router.project-osrm.org/route/v1/driving/"
    "{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
)
_TIMEOUT_S = 4.0


def fetch_road_route(origin: tuple[float, float], destination: tuple[float, float]) -> dict | None:
    """origin/destination are (lat, lon). Returns a GeoJSON LineString
    (road-snapped) on success, None on any failure - timeout, unreachable,
    no route found. Callers must fall back to a direct line rather than
    fail a dispatch decision over a routing API hiccup; the OSRM call is
    never in the critical path of who gets dispatched, only of how the
    route is drawn afterwards.
    """
    lat1, lon1 = origin
    lat2, lon2 = destination
    url = _OSRM_URL.format(lon1=lon1, lat1=lat1, lon2=lon2, lat2=lat2)
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT_S) as response:
            data = json.load(response)
    except Exception:
        return None

    if data.get("code") != "Ok" or not data.get("routes"):
        return None
    return data["routes"][0]["geometry"]
