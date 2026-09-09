"""Load the real data/raw/roads.geojson and settlements.geojson into
Supabase's road_segments/settlements tables.

Those tables exist (schema.sql) but were never populated - roads/isolation.py
and routers/roads.py were built against them, but /roads/isolation was
returning [] and /roads/demo/block was blocking "the first available
segment" (whichever row happened to be first) instead of the real NH6
segment, because there was no real data to look up. This script is what
was missing, not a fix to isolation.py itself.

osm_id is parsed from each feature's "@id" property ("way/242679584" ->
242679656) so routers/roads.py can look up DEMO_ROAD_BLOCK_TRIGGER's
way_id by exact match instead of guessing.
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]  # see services/api/.env - gitignored, never hardcode this

DATA_RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
ROADS_PATH = DATA_RAW_DIR / "roads.geojson"
SETTLEMENTS_PATH = DATA_RAW_DIR / "settlements.geojson"

_METERS_PER_DEGREE_LAT = 111_320.0


def _osm_id_from_at_id(at_id: str | None) -> int | None:
    if not at_id:
        return None
    m = re.search(r"(\d+)$", at_id)
    return int(m.group(1)) if m else None


def _linestring_length_m(coords: list[list[float]]) -> float:
    """Rough planar length in metres - fine for length_m's display purpose,
    not routing-grade geodesic precision."""
    mean_lat = sum(c[1] for c in coords) / len(coords)
    meters_per_deg_lon = _METERS_PER_DEGREE_LAT * math.cos(math.radians(mean_lat))
    total = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:]):
        dx = (lon2 - lon1) * meters_per_deg_lon
        dy = (lat2 - lat1) * _METERS_PER_DEGREE_LAT
        total += math.hypot(dx, dy)
    return total


def _linestring_wkt(coords: list[list[float]]) -> str:
    pts = ", ".join(f"{lon} {lat}" for lon, lat in coords)
    return f"LINESTRING({pts})"


def seed_roads(cur) -> int:
    with open(ROADS_PATH, encoding="utf-8") as f:
        roads = json.load(f)

    rows = []
    for feature in roads["features"]:
        geom = feature["geometry"]
        if geom["type"] != "LineString":
            continue
        coords = geom["coordinates"]
        if len(coords) < 2:
            continue
        props = feature["properties"]
        osm_id = _osm_id_from_at_id(props.get("@id"))
        rows.append((
            osm_id,
            _linestring_wkt(coords),
            props.get("highway"),
            _linestring_length_m(coords),
        ))

    execute_values(
        cur,
        """
        INSERT INTO road_segments (osm_id, geom, road_class, length_m)
        VALUES %s
        """,
        rows,
        template="(%s, ST_GeomFromText(%s, 4326), %s, %s)",
    )
    return len(rows)


def seed_settlements(cur) -> int:
    with open(SETTLEMENTS_PATH, encoding="utf-8") as f:
        settlements = json.load(f)

    rows = []
    for feature in settlements["features"]:
        geom = feature["geometry"]
        if geom["type"] != "Point":
            continue
        lon, lat = geom["coordinates"]
        props = feature["properties"]
        population = props.get("population")
        rows.append((
            props.get("name") or "Unnamed settlement",
            f"POINT({lon} {lat})",
            int(population) if population else None,
        ))

    execute_values(
        cur,
        """
        INSERT INTO settlements (name, geom, population)
        VALUES %s
        """,
        rows,
        template="(%s, ST_GeomFromText(%s, 4326), %s)",
    )
    return len(rows)


def main() -> None:
    if not ROADS_PATH.exists() or not SETTLEMENTS_PATH.exists():
        raise FileNotFoundError(
            f"{ROADS_PATH} or {SETTLEMENTS_PATH} not found - these must exist "
            f"before seeding (see ingest/osm.py / the overpass-turbo export)"
        )

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM road_segments")
            existing_roads = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM settlements")
            existing_settlements = cur.fetchone()[0]

            if existing_roads or existing_settlements:
                print(f"[seed] clearing {existing_roads} existing road_segments and "
                      f"{existing_settlements} existing settlements before reseeding")
                cur.execute("DELETE FROM road_segments")
                cur.execute("DELETE FROM settlements")

            n_roads = seed_roads(cur)
            n_settlements = seed_settlements(cur)
        conn.commit()
        print(f"[seed] inserted {n_roads} road segments and {n_settlements} settlements")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
