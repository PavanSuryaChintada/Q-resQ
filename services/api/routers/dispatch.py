"""Dispatch orchestration. See BUILD_SPEC.md and docs/WORKFLOW.md #4.

Wired to the real qubo_dispatch engine, not a fixture - the QUBO
formulation and solver chain are already built and tested in
packages/qubo-dispatch. Travel times fed to the solver are a straight-
line (haversine) estimate for every unit kind - fine as a cost signal
for comparing candidates, and computing a real routed time for every
unit-request pair the solver considers would mean hundreds of routing
calls per solve. The *rendered* route for an actual assignment is
different: wheeled units (ambulance/truck/team) get a real road-
following route from roads/routing.py, boats stay on a direct line.
Units and requests still live in the in-memory stores from
routers/units.py and routers/requests.py until those are wired to
Supabase.
"""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from qubo_dispatch import DispatchProblem, Request as QDRequest, Unit as QDUnit, solve_partitioned

from models import AssignmentOut, DispatchRoundOut, DispatchSolveRequest, ManualAssignRequest, UnitOut, RequestOut
from roads.routing import ROAD_KINDS, fetch_road_route
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


def _direct_route(unit: UnitOut, request: RequestOut) -> dict:
    return {
        "type": "LineString",
        "coordinates": [
            [unit.position[1], unit.position[0]],  # lon, lat for unit
            [request.location[1], request.location[0]],  # lon, lat for request
        ],
    }


def _build_route(unit: UnitOut, request: RequestOut) -> tuple[dict, str]:
    """(GeoJSON LineString, source). source is "road" for a real OSRM-
    routed path, "direct" for a straight line - boats always, or a
    wheeled unit when the routing API didn't return in time.
    """
    if unit.kind in ROAD_KINDS:
        road_route = fetch_road_route(unit.position, request.location)
        if road_route is not None:
            return road_route, "road"
    return _direct_route(unit, request), "direct"


def _build_routes_concurrently(
    pairs: list[tuple[UnitOut, RequestOut]],
) -> dict[tuple[UUID, UUID], tuple[dict, str]]:
    """Same as _build_route, but for a whole batch of assignments at once -
    each OSRM call is a blocking HTTP request, so a solve with several
    wheeled-unit assignments would otherwise serialise multiple seconds
    of network latency onto the response.
    """
    if not pairs:
        return {}
    with ThreadPoolExecutor(max_workers=min(8, len(pairs))) as pool:
        results = list(pool.map(lambda p: _build_route(*p), pairs))
    return {(unit.id, request.id): result for (unit, request), result in zip(pairs, results)}


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
    resolved = [
        (units_store.get(UUID(unit_id)), requests_store.get(UUID(request_id)), unit_id, request_id)
        for unit_id, request_id in result.assignments
    ]
    routes = _build_routes_concurrently([(u, r) for u, r, _, _ in resolved if u and r])

    assignments = []
    for unit, request, unit_id, request_id in resolved:
        route, route_source = routes.get((unit.id, request.id), (None, None)) if unit and request else (None, None)
        assignments.append(
            AssignmentOut(
                id=uuid4(),
                unit_id=UUID(unit_id),
                request_id=UUID(request_id),
                route=route,
                route_source=route_source,
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
        f"round {str(round_id)[:8]} solved · {len(assignments)} assignments · "
        f"{result.backend}{fallback_note} · {solve_s:.2f}s",
    )

    return round_out


@router.post("/assign", response_model=AssignmentOut)
def assign_one(payload: ManualAssignRequest) -> AssignmentOut:
    """Manually send one specific unit to one specific request, bypassing
    the solver entirely - an operator override for when the QUBO's batch
    trade-off isn't what's wanted for this one call. Recorded as its own
    single-assignment round (backend="manual") so it shows up in
    /dispatch/assignments and the ledger exactly like a solved round.
    """
    unit = units_store.get(payload.unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="unit not found")
    if unit.status != "available":
        raise HTTPException(status_code=409, detail=f"unit {unit.label} is not available (status: {unit.status})")

    request = requests_store.get(payload.request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="request not found")
    if request.status != "open":
        raise HTTPException(
            status_code=409, detail=f"request {str(request.id)[:8]} is not open (status: {request.status})"
        )

    route, route_source = _build_route(unit, request)
    assignment = AssignmentOut(
        id=uuid4(),
        unit_id=unit.id,
        request_id=request.id,
        route=route,
        route_source=route_source,
    )
    round_id = uuid4()
    _rounds[round_id] = DispatchRoundOut(
        id=round_id,
        started_at=datetime.now(timezone.utc),
        request_count=1,
        unit_count=1,
        backend="manual",
        fell_back=False,
        objective=None,
        solve_ms=0,
        assignments=[assignment],
    )

    units_store[unit.id] = unit.model_copy(update={"status": "assigned"})
    requests_store[request.id] = request.model_copy(update={"status": "assigned"})

    log_router.append(
        "dispatch",
        f"{unit.label} manually assigned to request {str(request.id)[:8]}",
    )

    return assignment


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
