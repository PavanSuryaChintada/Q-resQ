"""Road isolation endpoints: block/clear segments, get settlement isolation,
Realtime broadcast.

This router provides the API surface for roads/isolation.py's functionality.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from shapely.geometry import shape
from supabase import create_client, Client

from config import REGION
from roads.isolation import (
    RoadBlockage,
    SettlementIsolation,
    block_road_segment,
    clear_road_segment,
    compute_settlement_isolation,
    get_demo_trigger_segments,
    get_isolated_settlement_names_for_trigger,
)

router = APIRouter(tags=["roads"])

# Supabase client
supabase: Client = create_client(
    "https://bsftkkpdtsqcblnmwbfd.supabase.co",
    "sb_publishable_urAbb_UvLdvF2ORY5PC6_w_XZGT9-7O"
)


class BlockSegmentRequest(BaseModel):
    segment_id: int
    block_reason: Literal["predicted", "reported", "confirmed"]


class ClearSegmentRequest(BaseModel):
    segment_id: int


@router.get("/blocked")
async def list_blocked_segments() -> list[dict]:
    """All currently-blocked road segments, for the map to render every
    real blockage - not just whichever one the NH6 demo trigger set.
    """
    result = supabase.table("road_segments").select("*").eq("blocked", True).execute()
    return [
        {
            "id": seg["id"],
            "osm_id": seg.get("osm_id"),
            "road_class": seg.get("road_class"),
            "geom": seg.get("geom"),
            "block_reason": seg.get("block_reason"),
            "blocked_since": seg.get("blocked_since"),
        }
        for seg in result.data
    ]


@router.get("/nearest")
async def nearest_segment(lat: float, lon: float) -> dict:
    """The road segment nearest a point - for "block the road near this
    citizen report" or "search a settlement, block its access road"
    flows, where the officer has a location but not a segment id.

    Distance is to the segment's nearest vertex, not a true point-to-
    line distance - close enough to pick the right segment at road scale,
    not routing-grade.
    """
    result = supabase.table("road_segments").select("*").execute()
    segments = [s for s in result.data if s.get("geom")]
    if not segments:
        raise HTTPException(status_code=404, detail="no road segments in the database")

    def min_dist_sq(seg: dict) -> float:
        return min((c[0] - lon) ** 2 + (c[1] - lat) ** 2 for c in seg["geom"]["coordinates"])

    best = min(segments, key=min_dist_sq)
    return {
        "id": best["id"],
        "osm_id": best.get("osm_id"),
        "road_class": best.get("road_class"),
        "geom": best.get("geom"),
        "blocked": best.get("blocked", False),
        "block_reason": best.get("block_reason"),
        "distance_m": (min_dist_sq(best) ** 0.5) * 111_320,  # rough deg->m at this latitude
    }


@router.get("/isolation")
async def get_isolation() -> list[dict]:
    """Get current isolation state for all settlements."""
    try:
        # Fetch settlements from database
        result = supabase.table("settlements").select("*").execute()
        settlements = result.data

        # Fetch road segments
        result_segments = supabase.table("road_segments").select("*").execute()
        road_segments = result_segments.data

        # Convert to format expected by isolation module
        # Supabase's REST API returns PostGIS geometry columns as plain
        # GeoJSON dicts, not shapely objects - roads/isolation.py's
        # isinstance(geom, Point/LineString) checks need the real thing,
        # or every row is silently skipped and isolation always comes
        # back empty.
        settlements_dict = []
        for s in settlements:
            settlements_dict.append({
                "id": s["id"],
                "name": s["name"],
                "geom": shape(s["geom"]) if s.get("geom") else None,
                "population": s.get("population", 0),
                "isolated": s.get("isolated", False),
                "isolation_score": s.get("isolation_score", 0.0),
                "component_size": s.get("component_size", 1),
                "path_to_hq": s.get("path_to_hq", True),
                "updated_at": s.get("updated_at"),
            })

        segments_dict = []
        for seg in road_segments:
            segments_dict.append({
                "id": seg["id"],
                "osm_id": seg.get("osm_id"),
                "geom": shape(seg["geom"]) if seg.get("geom") else None,
                "blocked": seg.get("blocked", False),
                "block_reason": seg.get("block_reason"),
                "blocked_since": seg.get("blocked_since"),
            })

        # Compute isolation
        isolation_results = compute_settlement_isolation(settlements_dict, segments_dict, hq_location=REGION["hq"])

        # Update database with computed results - one batched upsert
        # instead of one request per settlement. 52 sequential
        # .update().execute() calls (one network round-trip each) was
        # what made every isolation check take 45-55 seconds.
        #
        # PostgREST's upsert still validates NOT NULL columns against the
        # INSERT branch of its INSERT ... ON CONFLICT DO UPDATE (Postgres
        # checks the row against every NOT NULL constraint before it even
        # looks at the conflict target), so geom - NOT NULL, no default -
        # has to be included even though it never actually changes here.
        geom_by_id = {s["id"]: s["geom"] for s in settlements}
        now = datetime.now().isoformat()
        supabase.table("settlements").upsert([
            {
                "id": result.id,
                "geom": geom_by_id.get(result.id),
                "isolated": result.isolated,
                "isolation_score": result.isolation_score,
                "component_size": result.component_size,
                "path_to_hq": result.path_to_hq,
                "updated_at": now,
            }
            for result in isolation_results
        ]).execute()

        return [
            {
                "id": r.id,
                "name": r.name,
                "population": r.population,
                "isolated": r.isolated,
                "isolation_score": r.isolation_score,
                "component_size": r.component_size,
                "path_to_hq": r.path_to_hq,
                "lon": r.lon,
                "lat": r.lat,
            }
            for r in isolation_results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute isolation: {str(e)}")


@router.post("/block")
async def block_segment(req: BlockSegmentRequest) -> dict:
    """Mark a road segment as blocked."""
    try:
        # Update in database
        supabase.table("road_segments").update({
            "blocked": True,
            "block_reason": req.block_reason,
            "blocked_since": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }).eq("id", req.segment_id).execute()

        # Get updated segments
        result = supabase.table("road_segments").select("*").eq("id", req.segment_id).execute()
        segments = result.data

        if not segments:
            raise HTTPException(status_code=404, detail="Segment not found")

        # Create blockage object
        segment = segments[0]
        blockage = RoadBlockage(
            segment_id=segment["id"],
            osm_id=segment.get("osm_id"),
            blocked=True,
            block_reason=req.block_reason,
            blocked_since=segment.get("blocked_since"),
        )

        # Recompute isolation
        await get_isolation()

        return {
            "segment_id": blockage.segment_id,
            "blocked": blockage.blocked,
            "block_reason": blockage.block_reason,
            "blocked_since": blockage.blocked_since,
            "geom": segment.get("geom"),
            "message": f"Segment {req.segment_id} blocked successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to block segment: {str(e)}")


@router.post("/clear")
async def clear_segment(req: ClearSegmentRequest) -> dict:
    """Mark a road segment as cleared (unblocked)."""
    try:
        # Update in database
        supabase.table("road_segments").update({
            "blocked": False,
            "block_reason": "cleared",
            "blocked_since": None,
            "updated_at": datetime.now().isoformat()
        }).eq("id", req.segment_id).execute()

        # Get updated segments
        result = supabase.table("road_segments").select("*").eq("id", req.segment_id).execute()
        segments = result.data

        if not segments:
            raise HTTPException(status_code=404, detail="Segment not found")

        segment = segments[0]
        blockage = RoadBlockage(
            segment_id=segment["id"],
            osm_id=segment.get("osm_id"),
            blocked=False,
            block_reason="cleared",
            blocked_since=None,
        )

        # Recompute isolation
        await get_isolation()

        return {
            "segment_id": blockage.segment_id,
            "blocked": blockage.blocked,
            "block_reason": blockage.block_reason,
            "message": f"Segment {req.segment_id} cleared successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear segment: {str(e)}")


@router.get("/demo/trigger")
async def get_demo_trigger() -> dict:
    """Get the demo isolation trigger configuration.

    Returns the OSM way ID and the settlements that become isolated when
    it's blocked, for the NH6 demo scenario.
    """
    from config import DEMO_ROAD_BLOCK_TRIGGER

    return {
        "way_id": DEMO_ROAD_BLOCK_TRIGGER["way_id"],
        "ref": DEMO_ROAD_BLOCK_TRIGGER["ref"],
        "isolated_settlements": DEMO_ROAD_BLOCK_TRIGGER["isolated_settlements"],
        "backup_way_id": DEMO_ROAD_BLOCK_TRIGGER.get("backup_way_id"),
    }


def _osm_id_from_way(way_id: str) -> int:
    """DEMO_ROAD_BLOCK_TRIGGER stores way_id as 'way/242679584' - road_segments.osm_id is the bare int."""
    return int(way_id.rsplit("/", 1)[-1])


@router.post("/demo/block")
async def block_demo_trigger() -> dict:
    """Block the real NH6 segment (config.DEMO_ROAD_BLOCK_TRIGGER) for the
    isolation demo - looked up by its actual OSM way id, not an arbitrary
    "first row" placeholder.
    """
    way_id = get_demo_trigger_segments()[0]
    isolated_settlements = get_isolated_settlement_names_for_trigger(way_id)
    osm_id = _osm_id_from_way(way_id)

    result = supabase.table("road_segments").select("id").eq("osm_id", osm_id).execute()
    if not result.data:
        raise HTTPException(
            status_code=404,
            detail=f"road_segments has no row with osm_id={osm_id} (way_id={way_id}) - "
                   f"run scripts/seed_roads_and_settlements.py",
        )

    demo_segment_id = result.data[0]["id"]
    block_result = await block_segment(BlockSegmentRequest(
        segment_id=demo_segment_id,
        block_reason="confirmed",
    ))

    return {
        "way_id": way_id,
        "segment_id": demo_segment_id,
        "blocked": True,
        "isolated_settlements": isolated_settlements,
        "geom": block_result.get("geom"),
        "message": f"Blocked way {way_id}. Settlements now isolated: {', '.join(isolated_settlements)}",
    }
