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

from fastapi import APIRouter, HTTPException

from models import RequestCategory, RequestCreate, RequestOut, SeedResult, UnitKind, UnitOut
from routers import log as log_router
from routers.requests import _store as requests_store
from routers.units import _store as units_store

router = APIRouter()

# matches risk/features.py's DEMO_BBOX, so seeded units/requests land
# where real computed risk cells actually exist
_LAT_RANGE = (18.20, 18.45)
_LON_RANGE = (83.75, 84.05)

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

# Request category mix per hazard type - same real Srikakulam geography
# and terrain (risk/heuristic.py:DISASTER_WEIGHTS re-weights the risk
# map for these same types), but who calls for what differs by hazard:
#   cyclone: storm surge strands people waiting for boats - the
#     BUILD_SPEC.md default.
#   flood: gradual rise, fewer emergency evacuations mid-event, more
#     people just stuck in place.
#   urban_flooding: more medical calls (traffic, electrocution risk)
#     and stranded vehicles, fewer full evacuations.
#   landslide: sudden-onset and structurally dangerous - much higher
#     evacuation share, less "wait it out."
_CATEGORY_WEIGHTS_BY_TYPE: dict[str, list[float]] = {
    "cyclone": [0.20, 0.50, 0.30],
    "flood": [0.20, 0.60, 0.20],
    "urban_flooding": [0.30, 0.55, 0.15],
    "landslide": [0.35, 0.15, 0.50],
}


@router.post("/titli", response_model=SeedResult)
def seed_titli(n_requests: int = 30, seed: int = 11102018, disaster_type: str = "cyclone") -> SeedResult:
    if disaster_type not in _CATEGORY_WEIGHTS_BY_TYPE:
        raise HTTPException(
            status_code=422,
            detail=f"unknown disaster_type {disaster_type!r}, expected one of {list(_CATEGORY_WEIGHTS_BY_TYPE)}",
        )
    category_weights = _CATEGORY_WEIGHTS_BY_TYPE[disaster_type]
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
        # Generate random severity (0-1) for demo purposes
        severity = rng.random()
        payload = RequestCreate(
            id=request_id,
            location=(rng.uniform(*_LAT_RANGE), rng.uniform(*_LON_RANGE)),
            people_count=rng.randint(1, 8),
            category=rng.choices(_CATEGORIES, weights=category_weights)[0],
            created_at=datetime.now(timezone.utc),
        )
        requests_store[request_id] = RequestOut(**payload.model_dump(), status="open", severity=severity)

    log_router.append(
        "system",
        f"seeded {disaster_type} scenario · {len(_UNIT_LABELS)} units · {n_requests} requests",
    )

    return SeedResult(status="seeded", units_created=len(_UNIT_LABELS), requests_created=n_requests)
