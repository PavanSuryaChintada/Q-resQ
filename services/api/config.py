"""Single source of truth for region and language constants. Every
module that needs the district bbox, grid resolution, or supported
languages imports from here - never redefines them.

Before this pivot, ingest/config.py and risk/features.py each
hardcoded their own, disagreeing, Srikakulam-specific bbox. Both now
import from here.
"""

from __future__ import annotations

REGION = {
    "name": "Aizawl district, Mizoram",
    "bbox": {"west": 92.55, "south": 23.55, "east": 93.05, "north": 24.05},
    "grid_m": 100,          # finer than the flood build's 250 m - hill terrain
    "crs": "EPSG:4326",
    "utm": "EPSG:32646",    # UTM zone 46N, for metric operations
    "hq": (23.7271, 92.7176),  # Aizawl - isolation scoring anchor
}

LANGUAGES = ["en", "hi", "as"]  # English, Hindi, Assamese - no others generated

INSAR_CORRIDOR = {
    "id": "aizawl-ridge-01",
    "description": "Set to the corridor actually processed. Do not guess.",
}

# Verified against the real roads.geojson graph (services/api/scripts/
# find_isolation_edge.py) - blocking this way is the only single-edge
# blockage in the whole graph that isolates 3 real, named settlements
# from REGION['hq']. NH6 is the Aizawl-Silchar route and closes to
# landslides most monsoons, so this is a recurring real event, not a
# constructed one. roads/isolation.py (not yet built) should treat this
# as the deterministic demo road-block trigger.
DEMO_ROAD_BLOCK_TRIGGER = {
    "way_id": "way/242679584",
    "highway": "trunk",
    "ref": "NH6",
    "isolated_settlements": ["Lenchim", "Tawizo", "Mualpheng"],
    "backup_way_id": "way/385151486",  # tertiary road, isolates the same 3 settlements via a different segment
}
