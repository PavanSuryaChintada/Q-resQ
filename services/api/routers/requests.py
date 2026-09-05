"""Rescue request intake and offline sync. See BUILD_SPEC.md.

The client generates the UUID; both endpoints upsert on it. A replayed
batch must be harmless - that's the entire conflict-resolution story.
In-memory for now (fixture stage); swapped for Supabase once wired to
real data.

Severity (dispatch/severity.py) is recomputed for the whole open
queue on every upsert and every list, since it's relative to the
current queue's own max people/wait - not a fixture.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException

from dispatch.severity import compute_severity
from models import RequestCreate, RequestOut, RequestPatch
from risk.features import nearest_risk_score
from routers import log as log_router

router = APIRouter()

_store: dict[UUID, RequestOut] = {}


def _recompute_open_severity() -> None:
    open_requests = [r for r in _store.values() if r.status == "open"]
    if not open_requests:
        return

    now = datetime.now(timezone.utc)
    waits = {r.id: max(0.0, (now - r.created_at).total_seconds() / 60.0) for r in open_requests}
    max_people = max(r.people_count for r in open_requests)
    max_wait = max(waits.values())

    for request in open_requests:
        area_risk = nearest_risk_score(request.location[0], request.location[1])
        result = compute_severity(
            people_count=request.people_count,
            category=request.category,
            area_risk=area_risk,
            wait_minutes=waits[request.id],
            max_people_in_queue=max_people,
            max_wait_minutes_in_queue=max_wait,
        )
        _store[request.id] = request.model_copy(update={
            "severity": result["severity"],
            "sev_people": result["sev_people"],
            "sev_category": result["sev_category"],
            "sev_area_risk": result["sev_area_risk"],
            "sev_wait": result["sev_wait"],
        })


def _upsert(payload: RequestCreate) -> RequestOut:
    existing = _store.get(payload.id)
    out = RequestOut(
        **payload.model_dump(),
        status=existing.status if existing else "open",
        severity=existing.severity if existing else None,
        sev_people=existing.sev_people if existing else None,
        sev_category=existing.sev_category if existing else None,
        sev_area_risk=existing.sev_area_risk if existing else None,
        sev_wait=existing.sev_wait if existing else None,
        synced_at=datetime.now(timezone.utc),
        resolved_at=existing.resolved_at if existing else None,
    )
    _store[payload.id] = out
    if existing is None:
        log_router.append("intake", f"request {str(payload.id)[:8]} queued")
    return out


@router.post("", response_model=RequestOut, status_code=201)
def create_request(payload: RequestCreate) -> RequestOut:
    result = _upsert(payload)
    _recompute_open_severity()
    return _store[result.id]


@router.get("", response_model=list[RequestOut])
def list_requests(status: str | None = None, limit: int = 100) -> list[RequestOut]:
    _recompute_open_severity()
    items = list(_store.values())
    if status is not None:
        items = [r for r in items if r.status == status]
    items.sort(key=lambda r: (r.severity or 0.0), reverse=True)
    return items[:limit]


@router.patch("/{request_id}", response_model=RequestOut)
def patch_request(request_id: UUID, payload: RequestPatch) -> RequestOut:
    existing = _store.get(request_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="request not found")
    updated = existing.model_copy(update={"status": payload.status})
    _store[request_id] = updated
    return updated


@router.post("/sync", response_model=list[RequestOut])
def sync_requests(payload: list[RequestCreate]) -> list[RequestOut]:
    results = [_upsert(item) for item in payload]
    _recompute_open_severity()
    return [_store[r.id] for r in results]
