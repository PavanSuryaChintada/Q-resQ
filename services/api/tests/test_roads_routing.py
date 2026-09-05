"""roads/routing.py must never let a routing-API problem break a
dispatch decision - fetch_road_route has to return None (not raise)
on any failure, so callers can fall back to a direct line.
"""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import patch

from roads.routing import fetch_road_route


class _FakeResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode()

    def __enter__(self):
        return BytesIO(self._body)

    def __exit__(self, *exc):
        return False


def test_returns_the_geojson_geometry_on_a_successful_route():
    payload = {
        "code": "Ok",
        "routes": [{"geometry": {"type": "LineString", "coordinates": [[83.9, 18.3], [83.95, 18.32]]}}],
    }
    with patch("urllib.request.urlopen", return_value=_FakeResponse(payload)):
        geometry = fetch_road_route((18.3, 83.9), (18.32, 83.95))
    assert geometry == {"type": "LineString", "coordinates": [[83.9, 18.3], [83.95, 18.32]]}


def test_returns_none_when_osrm_reports_no_route():
    payload = {"code": "NoRoute", "routes": []}
    with patch("urllib.request.urlopen", return_value=_FakeResponse(payload)):
        assert fetch_road_route((18.3, 83.9), (18.32, 83.95)) is None


def test_returns_none_on_any_network_failure_rather_than_raising():
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        assert fetch_road_route((18.3, 83.9), (18.32, 83.95)) is None


def test_returns_none_on_malformed_response_rather_than_raising():
    with patch("urllib.request.urlopen", return_value=_FakeResponse({"unexpected": "shape"})):
        assert fetch_road_route((18.3, 83.9), (18.32, 83.95)) is None
