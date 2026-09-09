"""Citizen reports endpoints.

This router provides the API surface for reports/clustering.py's functionality.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client

from reports.clustering import (
    CitizenReport,
    ReportCluster,
    cluster_reports,
    deduplicate_reports,
    get_hotspots,
)

router = APIRouter(tags=["reports"])

# Supabase client
supabase: Client = create_client(
    "https://bsftkkpdtsqcblnmwbfd.supabase.co",
    "sb_publishable_urAbb_UvLdvF2ORY5PC6_w_XZGT9-7O"
)

ReportStatus = Literal["pending", "verified", "dismissed", "duplicate"]


class ReportCreate(BaseModel):
    id: UUID
    location: tuple[float, float]  # (lat, lon)
    accuracy_m: float | None = None
    kind: Literal["crack", "slope_movement", "road_blocked", "water_seepage", "other"]
    auto_class: str | None = None
    auto_conf: float | None = None
    note: str | None = None
    media_url: str | None = None
    media_type: Literal["image", "video"] | None = None
    reporter_hash: str
    lang: str
    created_at: datetime


class ReportOut(BaseModel):
    id: str
    location: tuple[float, float]
    accuracy_m: float | None
    kind: str
    auto_class: str | None
    auto_conf: float | None
    note: str | None
    media_url: str | None
    media_type: str | None
    status: ReportStatus
    cluster_id: int | None
    reporter_hash: str
    lang: str
    created_at: datetime
    synced_at: datetime
    reviewed_at: datetime | None


class ClusterOut(BaseModel):
    id: int
    centroid_lat: float
    centroid_lon: float
    report_count: int
    first_seen: datetime
    last_seen: datetime
    dominant_kind: str


class ReportPatch(BaseModel):
    status: ReportStatus


# Supabase client (TODO: wire to actual DB)
# For now, use in-memory storage for demo
_reports_storage: list[CitizenReport] = []
_clusters_storage: list[ReportCluster] = []


@router.post("/")
async def create_report(req: ReportCreate) -> ReportOut:
    """Create a new citizen report."""
    global _reports_storage, _clusters_storage
    try:
        # Insert into Supabase
        report_data = {
            "id": str(req.id),
            "location": f"POINT({req.location[1]} {req.location[0]})",  # PostGIS Point format: lon lat
            "accuracy_m": req.accuracy_m,
            "kind": req.kind,
            "auto_class": req.auto_class,
            "auto_conf": req.auto_conf,
            "note": req.note,
            "media_url": req.media_url,
            "media_type": req.media_type,
            "status": "pending",
            "cluster_id": None,
            "reporter_hash": req.reporter_hash,
            "lang": req.lang,
            "created_at": req.created_at.isoformat(),
            "synced_at": datetime.now().isoformat(),
        }

        result = supabase.table("citizen_reports").insert(report_data).execute()

        # Convert to internal model for clustering
        report = CitizenReport(
            id=str(req.id),
            location=req.location,
            accuracy_m=req.accuracy_m,
            kind=req.kind,
            auto_class=req.auto_class,
            auto_conf=req.auto_conf,
            note=req.note,
            media_url=req.media_url,
            media_type=req.media_type,
            status="pending",
            cluster_id=None,
            reporter_hash=req.reporter_hash,
            lang=req.lang,
            created_at=req.created_at,
            synced_at=datetime.now(),
            reviewed_at=None,
        )

        # Add to in-memory storage for clustering
        _reports_storage.append(report)

        # Re-run clustering
        clusters, updated_reports = cluster_reports(_reports_storage)
        _clusters_storage = clusters
        _reports_storage = updated_reports

        # Re-run deduplication
        _reports_storage = deduplicate_reports(_reports_storage)

        # Update cluster_id in database
        for r in updated_reports:
            if r.cluster_id is not None:
                supabase.table("citizen_reports").update({
                    "cluster_id": r.cluster_id,
                    "status": r.status
                }).eq("id", r.id).execute()

        # Return the updated report
        updated_report = next(r for r in _reports_storage if r.id == report.id)
        return _report_to_out(updated_report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create report: {str(e)}")


@router.get("/")
async def list_reports(
    status: ReportStatus | None = None,
    limit: int = 100,
) -> list[ReportOut]:
    """List citizen reports, optionally filtered by status."""
    reports = _reports_storage

    if status is not None:
        reports = [r for r in reports if r.status == status]

    # Sort by created_at descending
    reports = sorted(reports, key=lambda r: r.created_at, reverse=True)

    # Apply limit
    reports = reports[:limit]

    return [_report_to_out(r) for r in reports]


@router.get("/{report_id}")
async def get_report(report_id: str) -> ReportOut:
    """Get a specific report by ID."""
    report = next((r for r in _reports_storage if r.id == report_id), None)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_to_out(report)


@router.patch("/{report_id}")
async def update_report(report_id: str, req: ReportPatch) -> ReportOut:
    """Update a report's status (for officer review)."""
    report = next((r for r in _reports_storage if r.id == report_id), None)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report.status = req.status
    if req.status in ["verified", "dismissed"]:
        report.reviewed_at = datetime.now()

    return _report_to_out(report)


@router.get("/clusters/")
async def list_clusters(min_reports: int = 3) -> list[ClusterOut]:
    """List report clusters, optionally filtered by hotspot threshold."""
    clusters = get_hotspots(_clusters_storage, min_reports)
    return [_cluster_to_out(c) for c in clusters]


@router.get("/clusters/{cluster_id}")
async def get_cluster(cluster_id: int) -> ClusterOut:
    """Get a specific cluster by ID."""
    cluster = next((c for c in _clusters_storage if c.id == cluster_id), None)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return _cluster_to_out(cluster)


@router.get("/clusters/{cluster_id}/reports")
async def get_cluster_reports(cluster_id: int) -> list[ReportOut]:
    """Get all reports in a specific cluster."""
    reports = [r for r in _reports_storage if r.cluster_id == cluster_id]
    return [_report_to_out(r) for r in reports]


@router.delete("/")
async def clear_demo_data() -> dict:
    """Clear all demo reports and clusters (for testing)."""
    global _reports_storage, _clusters_storage
    _reports_storage = []
    _clusters_storage = []
    return {"status": "cleared"}


def _report_to_out(report: CitizenReport) -> ReportOut:
    return ReportOut(
        id=report.id,
        location=report.location,
        accuracy_m=report.accuracy_m,
        kind=report.kind,
        auto_class=report.auto_class,
        auto_conf=report.auto_conf,
        note=report.note,
        media_url=report.media_url,
        media_type=report.media_type,
        status=report.status,  # type: ignore
        cluster_id=report.cluster_id,
        reporter_hash=report.reporter_hash,
        lang=report.lang,
        created_at=report.created_at,
        synced_at=report.synced_at,
        reviewed_at=report.reviewed_at,
    )


def _cluster_to_out(cluster: ReportCluster) -> ClusterOut:
    return ClusterOut(
        id=cluster.id,
        centroid_lat=cluster.centroid_lat,
        centroid_lon=cluster.centroid_lon,
        report_count=cluster.report_count,
        first_seen=cluster.first_seen,
        last_seen=cluster.last_seen,
        dominant_kind=cluster.dominant_kind,
    )
