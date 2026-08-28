"""Rescue unit status and position. See BUILD_SPEC.md.

In-memory for now (fixture stage); swapped for Supabase once wired to
real data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException

from models import UnitOut, UnitPatch

router = APIRouter()

_store: dict[UUID, UnitOut] = {}


def _seed() -> None:
    if _store:
        return
    now = datetime.now(timezone.utc)
    for unit in [
        UnitOut(id=uuid4(), label="Boat 03", kind="boat", capacity=6,
                position=(18.3021, 83.8912), status="available", updated_at=now),
        UnitOut(id=uuid4(), label="Boat 07", kind="boat", capacity=4,
                position=(18.2894, 83.9033), status="available", updated_at=now),
        UnitOut(id=uuid4(), label="Ambulance 02", kind="ambulance", capacity=2,
                position=(18.2967, 83.8977), status="available", updated_at=now),
    ]:
        _store[unit.id] = unit


_seed()


@router.get("", response_model=list[UnitOut])
def list_units() -> list[UnitOut]:
    return list(_store.values())


@router.patch("/{unit_id}", response_model=UnitOut)
def patch_unit(unit_id: UUID, payload: UnitPatch) -> UnitOut:
    existing = _store.get(unit_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="unit not found")
    updates = payload.model_dump(exclude_unset=True)
    updates["updated_at"] = datetime.now(timezone.utc)
    updated = existing.model_copy(update=updates)
    _store[unit_id] = updated
    return updated
