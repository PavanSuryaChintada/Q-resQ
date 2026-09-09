"""InSAR deformation endpoints.

This router provides the API surface for insar/deformation.py's functionality.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from insar.deformation import (
    DeformationPoint,
    DeformationSeries,
    InsarCorridor,
    get_accelerating_points,
    get_corridors,
    get_deformation_points,
    get_deformation_series,
)

router = APIRouter(tags=["insar"])


class DeformationPointOut(BaseModel):
    id: int
    lon: float
    lat: float
    corridor_id: str
    velocity_mm_yr: float
    coherence: float
    acceleration: float
    alert_state: str
    n_acquisitions: int
    first_date: str
    last_date: str
    synthetic: bool  # Explicit flag for synthetic vs measured data


class DeformationSeriesOut(BaseModel):
    point_id: int
    acq_date: str
    displacement_mm: float


class InsarCorridorOut(BaseModel):
    id: str
    description: str
    track: int
    orbit_dir: str
    n_scenes: int


@router.get("/points")
async def list_deformation_points(corridor_id: str | None = None) -> list[DeformationPointOut]:
    """Get all deformation points, optionally filtered by corridor.

    Low-coherence points (< 0.3) are filtered out automatically.
    """
    points = get_deformation_points(corridor_id)
    return [
        DeformationPointOut(
            id=p.id,
            lon=p.lon,
            lat=p.lat,
            corridor_id=p.corridor_id,
            velocity_mm_yr=p.velocity_mm_yr,
            coherence=p.coherence,
            acceleration=p.acceleration,
            alert_state=p.alert_state,
            n_acquisitions=p.n_acquisitions,
            first_date=p.first_date,
            last_date=p.last_date,
            synthetic=getattr(p, "synthetic", False),  # Include synthetic flag
        )
        for p in points
    ]


@router.get("/points/{point_id}/series")
async def get_point_series(point_id: int) -> list[DeformationSeriesOut]:
    """Get time series for a specific deformation point."""
    series = get_deformation_series(point_id)
    if not series:
        raise HTTPException(status_code=404, detail=f"Point {point_id} not found")

    return [
        DeformationSeriesOut(
            point_id=s.point_id,
            acq_date=s.acq_date,
            displacement_mm=s.displacement_mm,
        )
        for s in series
    ]


@router.get("/corridors")
async def list_corridors() -> list[InsarCorridorOut]:
    """Get all processed InSAR corridors."""
    corridors = get_corridors()
    return [
        InsarCorridorOut(
            id=c.id,
            description=c.description,
            track=c.track,
            orbit_dir=c.orbit_dir,
            n_scenes=c.n_scenes,
        )
        for c in corridors
    ]


@router.get("/alerts")
async def list_alerts(corridor_id: str | None = None) -> list[DeformationPointOut]:
    """Get points with accelerating deformation (alert state).

    These are the points that should trigger alerts for officers.
    """
    points = get_accelerating_points(corridor_id)
    return [
        DeformationPointOut(
            id=p.id,
            lon=p.lon,
            lat=p.lat,
            corridor_id=p.corridor_id,
            velocity_mm_yr=p.velocity_mm_yr,
            coherence=p.coherence,
            acceleration=p.acceleration,
            alert_state=p.alert_state,
            n_acquisitions=p.n_acquisitions,
            first_date=p.first_date,
            last_date=p.last_date,
            synthetic=getattr(p, "synthetic", False),
        )
        for p in points
    ]


@router.get("/demo/status")
async def get_demo_status() -> dict:
    """Get the demo InSAR status information.

    Returns information about the demo corridor and data availability.
    """
    corridors = get_corridors()
    points = get_deformation_points()
    alerts = get_accelerating_points()

    # Check if any synthetic data
    synthetic_count = sum(1 for p in points if getattr(p, "synthetic", False))

    return {
        "corridors": len(corridors),
        "total_points": len(points),
        "alert_points": len(alerts),
        "synthetic_points": synthetic_count,
        "corridor_id": corridors[0].id if corridors else None,
        "description": corridors[0].description if corridors else "No corridor data available",
        "important": "Deformation data is SYNTHETIC DEMONSTRATION DATA pending real SLC acquisition for Aizawl. The processing pipeline is built and ready for real interferogram processing. Points marked with synthetic=true are generated for illustration only.",
    }
