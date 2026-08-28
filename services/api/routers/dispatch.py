"""Dispatch orchestration. See BUILD_SPEC.md and docs/WORKFLOW.md #4.

Wired to the real qubo_dispatch engine, not a fixture - the QUBO
formulation and solver chain are already built and tested in
packages/qubo-dispatch. Travel times are a straight-line placeholder
(haversine) until roads/graph.py exists; units and requests still
live in the in-memory stores from routers/units.py and
routers/requests.py until those are wired to Supabase.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from qubo_dispatch import DispatchProblem, Request as QDRequest, Unit as QDUnit, solve_partitioned

from models import AssignmentOut, DispatchRoundOut, DispatchSolveRequest
from routers import log as log_router
from routers.requests import _store as requests_store
from routers.units import _store as units_store

router = APIRouter()

_rounds: dict[UUID, DispatchRoundOut] = {}

_DEFAULT_BOAT_SPEED_KMH = 15.0


def _haversine_travel_s(a: tuple[float, float], b: tuple[float, float],
                         speed_kmh: float = _DEFAULT_BOAT_SPEED_KMH) -> float:
    earth_radius_km = 6371.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    distance_km = 2 * earth_radius_km * math.asin(math.sqrt(h))
    return (distance_km / speed_kmh) * 3600.0


def build_current_problem(max_requests: int | None = None, max_units: int | None = None) -> DispatchProblem:
    """Snapshot open requests + available units into a DispatchProblem.

    Raises HTTPException(422) if there's nothing to solve. Shared with
    routers/benchmark.py so both read the same live state the same way.

    max_requests/max_units cap the snapshot to the highest-severity
    subset - used by benchmark.py to keep the comparison within qaoa's
    24-qubit statevector guard (CLAUDE.md's target zone size: 4 units
    x 5 requests = 20 qubits) rather than the whole open queue, which
    routinely has far more variables than qaoa can ever run on
    unpartitioned.
    """
    open_requests = [r for r in requests_store.values() if r.status == "open"]
    available_units = [u for u in units_store.values() if u.status == "available"]

    if not open_requests or not available_units:
        raise HTTPException(status_code=422, detail="no open requests or no available units to dispatch")

    if max_requests is not None:
        open_requests = sorted(open_requests, key=lambda r: r.severity or 0.0, reverse=True)[:max_requests]
    if max_units is not None:
        available_units = available_units[:max_units]

    qd_units = [QDUnit(id=str(u.id), capacity=u.capacity, position=u.position, kind=u.kind)
                for u in available_units]
    # severity defaults to 0.5 until dispatch/severity.py (Stage 04
    # triage) exists and populates it on intake
    qd_requests = [QDRequest(id=str(r.id), severity=r.severity if r.severity is not None else 0.5,
                              people=r.people_count, position=r.location)
                   for r in open_requests]
    travel_time_s = {
        (u.id, r.id): _haversine_travel_s(u.position, r.position)
        for u in qd_units for r in qd_requests
    }
    return DispatchProblem(units=qd_units, requests=qd_requests, travel_time_s=travel_time_s)


@router.post("/solve", response_model=DispatchRoundOut)
def solve_dispatch(payload: DispatchSolveRequest) -> DispatchRoundOut:
    problem = build_current_problem()
    result = solve_partitioned(problem, backend=payload.backend, timeout_s=payload.timeout_s,
                                max_requests_per_zone=5, max_units_per_zone=4)

    round_id = uuid4()
    assignments = []
    for unit_id, request_id in result.assignments:
        unit = units_store.get(UUID(unit_id))
        request = requests_store.get(UUID(request_id))
        route = None
        if unit and request:
            # Create simple straight-line route as GeoJSON LineString
            route = {
                "type": "LineString",
                "coordinates": [
                    [unit.position[1], unit.position[0]],  # lon, lat for unit
                    [request.location[1], request.location[0]],  # lon, lat for request
                ]
            }
        assignments.append(
            AssignmentOut(
                id=uuid4(),
                unit_id=UUID(unit_id),
                request_id=UUID(request_id),
                route=route
            )
        )
    round_out = DispatchRoundOut(
        id=round_id,
        started_at=datetime.now(timezone.utc),
        request_count=len(problem.requests),
        unit_count=len(problem.units),
        backend=result.backend,
        fell_back=result.fell_back,
        objective=result.objective,
        solve_ms=result.solve_ms,
        assignments=assignments,
    )
    _rounds[round_id] = round_out

    for assignment in assignments:
        units_store[assignment.unit_id] = units_store[assignment.unit_id].model_copy(
            update={"status": "assigned"})
        requests_store[assignment.request_id] = requests_store[assignment.request_id].model_copy(
            update={"status": "assigned"})

    solve_s = (result.solve_ms or 0) / 1000.0
    fallback_note = " (fell back)" if result.fell_back else ""
    log_router.append(
        "dispatch",
        f"round {round_id} solved · {len(assignments)} assignments · "
        f"{result.backend}{fallback_note} · {solve_s:.2f}s",
    )

    return round_out


@router.get("/rounds/{round_id}", response_model=DispatchRoundOut)
def get_round(round_id: UUID) -> DispatchRoundOut:
    round_out = _rounds.get(round_id)
    if round_out is None:
        raise HTTPException(status_code=404, detail="dispatch round not found")
    return round_out


@router.get("/assignments", response_model=list[AssignmentOut])
def get_assignments() -> list[AssignmentOut]:
    """Return all assignments from all dispatch rounds."""
    all_assignments: list[AssignmentOut] = []
    for round_out in _rounds.values():
        all_assignments.extend(round_out.assignments)
    return all_assignments
