"""Demo scenario loader. See BUILD_SPEC.md and docs/PRD.md #5.

Placeholder scale for now: a plausible unit/request layout around
Srikakulam, not yet the real Cyclone Titli scenario. The full
generator (real IMD track, NASA POWER rainfall, OSM facility pull,
HAND-weighted request placement) is seed/titli.py in the build order
(BUILD_SPEC.md step 8) - it needs the risk model and road graph
first, neither of which exist yet.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter

from models import RequestCategory, RequestCreate, RequestOut, SeedResult, UnitKind, UnitOut
from routers import log as log_router
from routers.requests import _store as requests_store
from routers.units import _store as units_store

router = APIRouter()

# Srikakulam district bounding box, roughly
_LAT_RANGE = (18.10, 18.85)
_LON_RANGE = (83.60, 84.20)

_UNIT_LABELS: list[tuple[str, UnitKind, int]] = [
    ("Boat 01", "boat", 6), ("Boat 02", "boat", 6), ("Boat 03", "boat", 6),
    ("Boat 04", "boat", 4), ("Boat 05", "boat", 4), ("Boat 06", "boat", 4),
    ("Boat 07", "boat", 4), ("Boat 08", "boat", 4),
    ("Ambulance 01", "ambulance", 2), ("Ambulance 02", "ambulance", 2),
    ("Ambulance 03", "ambulance", 2), ("Ambulance 04", "ambulance", 2),
    ("Truck 01", "truck", 8), ("Truck 02", "truck", 8),
    ("Rescue Team Alpha", "team", 10),
]

_CATEGORIES: list[RequestCategory] = ["medical", "stranded", "evacuation"]
_CATEGORY_WEIGHTS = [0.20, 0.50, 0.30]  # per docs BUILD_SPEC.md seed/titli.py


@router.post("/titli", response_model=SeedResult)
def seed_titli(n_requests: int = 30, seed: int = 11102018) -> SeedResult:
    rng = random.Random(seed)

    units_store.clear()
    for label, kind, capacity in _UNIT_LABELS:
        unit = UnitOut(
            id=uuid4(), label=label, kind=kind, capacity=capacity,
            position=(rng.uniform(*_LAT_RANGE), rng.uniform(*_LON_RANGE)),
            status="available", updated_at=datetime.now(timezone.utc),
        )
        units_store[unit.id] = unit

    requests_store.clear()
    for _ in range(n_requests):
        request_id = uuid4()
        payload = RequestCreate(
            id=request_id,
            location=(rng.uniform(*_LAT_RANGE), rng.uniform(*_LON_RANGE)),
            people_count=rng.randint(1, 8),
            category=rng.choices(_CATEGORIES, weights=_CATEGORY_WEIGHTS)[0],
            created_at=datetime.now(timezone.utc),
        )
        requests_store[request_id] = RequestOut(**payload.model_dump(), status="open")

    log_router.append(
        "system",
        f"seeded titli scenario · {len(_UNIT_LABELS)} units · {n_requests} requests",
    )

    return SeedResult(status="seeded", units_created=len(_UNIT_LABELS), requests_created=n_requests)
