"""Resource pool management endpoints.

Admin can manage available resources (ambulances, rescue teams, trucks, etc.).
These resources are used for dynamic allocation optimization.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client

router = APIRouter(prefix="/resources", tags=["resources"])

# Supabase client
supabase: Client = create_client(
    "https://bsftkkpdtsqcblnmwbfd.supabase.co",
    "sb_publishable_urAbb_UvLdvF2ORY5PC6_w_XZGT9-7O"
)

ResourceKind = Literal["ambulance", "rescue_team", "truck", "excavator", "helicopter", "boat"]


class ResourceCreate(BaseModel):
    kind: ResourceKind
    available: int
    total: int
    location: tuple[float, float] | None = None  # (lat, lon)


class ResourceUpdate(BaseModel):
    available: int | None = None
    total: int | None = None
    location: tuple[float, float] | None = None


class ResourceOut(BaseModel):
    id: int
    kind: str
    available: int
    total: int
    location: tuple[float, float] | None
    updated_at: str


@router.get("/")
async def list_resources() -> list[ResourceOut]:
    """Get all resources in the pool."""
    try:
        result = supabase.table("resource_pool").select("*").execute()
        return [
            {
                "id": r["id"],
                "kind": r["kind"],
                "available": r["available"],
                "total": r["total"],
                "location": None,  # Parse PostGIS if needed
                "updated_at": r["updated_at"]
            }
            for r in result.data
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch resources: {str(e)}")


@router.post("/")
async def create_resource(req: ResourceCreate) -> ResourceOut:
    """Add a new resource type to the pool."""
    try:
        geom = None
        if req.location:
            # PostGIS Point format: lon lat
            geom = f"POINT({req.location[1]} {req.location[0]})"

        resource_data = {
            "kind": req.kind,
            "available": req.available,
            "total": req.total,
            "location": geom,
            "updated_at": datetime.now().isoformat()
        }

        result = supabase.table("resource_pool").insert(resource_data).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create resource")

        created = result.data[0]
        return {
            "id": created["id"],
            "kind": created["kind"],
            "available": created["available"],
            "total": created["total"],
            "location": req.location,
            "updated_at": created["updated_at"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create resource: {str(e)}")


@router.patch("/{resource_id}")
async def update_resource(resource_id: int, req: ResourceUpdate) -> ResourceOut:
    """Update resource availability or location."""
    try:
        update_data = {}
        if req.available is not None:
            update_data["available"] = req.available
        if req.total is not None:
            update_data["total"] = req.total
        if req.location is not None:
            update_data["location"] = f"POINT({req.location[1]} {req.location[0]})"
        update_data["updated_at"] = datetime.now().isoformat()

        result = supabase.table("resource_pool").update(update_data).eq("id", resource_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Resource not found")

        updated = result.data[0]
        return {
            "id": updated["id"],
            "kind": updated["kind"],
            "available": updated["available"],
            "total": updated["total"],
            "location": req.location,
            "updated_at": updated["updated_at"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update resource: {str(e)}")


@router.delete("/{resource_id}")
async def delete_resource(resource_id: int) -> dict:
    """Delete a resource from the pool."""
    try:
        result = supabase.table("resource_pool").delete().eq("id", resource_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Resource not found")

        return {"message": f"Resource {resource_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete resource: {str(e)}")


@router.get("/available/{kind}")
async def get_available_by_kind(kind: ResourceKind) -> dict:
    """Get available count for a specific resource kind."""
    try:
        result = supabase.table("resource_pool").select("available").eq("kind", kind).execute()

        if not result.data:
            return {"kind": kind, "available": 0}

        total_available = sum(r["available"] for r in result.data)
        return {"kind": kind, "available": total_available}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch available resources: {str(e)}")
