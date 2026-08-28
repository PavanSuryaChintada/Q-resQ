"""Rescue request intake and offline sync. See BUILD_SPEC.md.

The client generates the UUID; both endpoints upsert on it. A replayed
batch must be harmless - that's the entire conflict-resolution story.
In-memory for now (fixture stage); swapped for Supabase once wired to
real data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException

from models import RequestCreate, RequestOut, RequestPatch
from routers import log as log_router

router = APIRouter()

_store: dict[UUID, RequestOut] = {}


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
        log_router.append("intake", f"{payload.id} queued")
    return out


@router.post("", response_model=RequestOut, status_code=201)
def create_request(payload: RequestCreate) -> RequestOut:
    return _upsert(payload)


@router.get("", response_model=list[RequestOut])
def list_requests(status: str | None = None, limit: int = 100) -> list[RequestOut]:
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
    return [_upsert(item) for item in payload]
