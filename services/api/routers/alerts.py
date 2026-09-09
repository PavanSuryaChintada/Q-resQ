"""Alerts endpoints - CAP generation and management.

This router provides the API surface for alerts/cap.py's functionality.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client

from alerts.cap import CapAlert, generate_deformation_alert, generate_landslide_alert

router = APIRouter(tags=["alerts"])

# Supabase client
supabase: Client = create_client(
    "https://bsftkkpdtsqcblnmwbfd.supabase.co",
    "sb_publishable_urAbb_UvLdvF2ORY5PC6_w_XZGT9-7O"
)


class AlertCreate(BaseModel):
    severity: int  # 0-4 (IMD ladder)
    headline: str
    area_name: str
    trigger_src: Literal["risk_band", "deformation", "report", "manual"]
    language: str = "en"
    geofence: list[tuple[float, float]] | None = None  # List of (lat, lon) tuples
    expires_hours: int = 24


class AlertOut(BaseModel):
    id: str
    cap_xml: str
    severity: int
    headline: str
    description: str
    trigger_src: str
    languages: list[str]
    issued_at: datetime
    expires_at: datetime


# Supabase client (TODO: wire to actual DB)
_alerts_storage: list[CapAlert] = []


@router.post("/")
async def create_alert(req: AlertCreate) -> AlertOut:
    """Create a new alert based on risk band or deformation."""
    try:
        if req.language not in ["en", "hi", "as"]:
            raise HTTPException(status_code=400, detail="Unsupported language. Use en, hi, or as")

        if req.trigger_src == "deformation":
            alert = generate_deformation_alert(
                corridor_id="demo",
                area_name=req.area_name,
                geofence=req.geofence,
                language=req.language,
                issued_at=datetime.now(),
            )
        else:
            alert = generate_landslide_alert(
                risk_band=req.severity,
                area_name=req.area_name,
                geofence=req.geofence,
                trigger_src=req.trigger_src,
                language=req.language,
                issued_at=datetime.now(),
                expires_hours=req.expires_hours,
            )

        # Insert into Supabase
        alert_data = {
            "cap_xml": alert.cap_xml,
            "severity": alert.severity,
            "headline": alert.headline,
            "description": alert.description,
            "geofence": f"POLYGON(({', '.join([f'{c[1]} {c[0]}' for c in alert.geofence])}))" if alert.geofence else None,
            "languages": alert.languages,
            "trigger_src": alert.trigger_src,
            "issued_at": alert.issued_at.isoformat(),
            "expires_at": alert.expires_at.isoformat(),
        }

        result = supabase.table("alerts").insert(alert_data).execute()

        _alerts_storage.append(alert)
        return _alert_to_out(alert)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create alert: {str(e)}")


@router.get("/")
async def list_alerts(limit: int = 50) -> list[AlertOut]:
    """List all alerts, most recent first."""
    alerts = sorted(_alerts_storage, key=lambda a: a.issued_at, reverse=True)
    alerts = alerts[:limit]
    return [_alert_to_out(a) for a in alerts]


@router.get("/{alert_id}")
async def get_alert(alert_id: str) -> AlertOut:
    """Get a specific alert by ID."""
    alert = next((a for a in _alerts_storage if a.id == alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _alert_to_out(alert)


@router.get("/{alert_id}/xml")
async def get_alert_xml(alert_id: str) -> str:
    """Get the CAP XML for a specific alert."""
    alert = next((a for a in _alerts_storage if a.id == alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert.cap_xml


@router.delete("/")
async def clear_demo_data() -> dict:
    """Clear all demo alerts (for testing)."""
    global _alerts_storage
    _alerts_storage = []
    return {"status": "cleared"}


@router.get("/demo/sample")
async def get_sample_alert() -> AlertOut:
    """Get a sample alert for demo purposes."""
    alert = generate_landslide_alert(
        risk_band=2,  # Alert level
        area_name="Aizawl District",
        trigger_src="risk_band",
        language="en",
        issued_at=datetime.now(),
    )
    return _alert_to_out(alert)


def _alert_to_out(alert: CapAlert) -> AlertOut:
    return AlertOut(
        id=alert.id,
        cap_xml=alert.cap_xml,
        severity=alert.severity,
        headline=alert.headline,
        description=alert.description,
        trigger_src=alert.trigger_src,
        languages=alert.languages,
        issued_at=alert.issued_at,
        expires_at=alert.expires_at,
    )
