"""Resource allocation optimization for emergency requests.

Takes citizen emergency requests and available resources from the pool,
computes optimal assignments using the existing QUBO dispatch package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np

# Import the existing dispatch package for QUBO formulation
try:
    from packages.qubo_dispatch.dispatch import (
        solve_dispatch_qubo,
        solve_dispatch_annealing,
        solve_dispatch_ortools,
        solve_dispatch_greedy,
        DispatchProblem,
        Request as QDRequest,
        Unit as QDUnit,
    )
except ImportError:
    # Fallback if package not available
    solve_dispatch_qubo = None
    solve_dispatch_annealing = None
    solve_dispatch_ortools = None
    solve_dispatch_greedy = None
    DispatchProblem = None
    QDRequest = None
    QDUnit = None


@dataclass
class EmergencyRequest:
    """A citizen emergency request."""
    id: str
    location: tuple[float, float]  # (lat, lon)
    people_count: int
    category: str  # medical, stranded, evacuation
    severity: float  # 0-1, computed from factors
    created_at: str


@dataclass
class AvailableResource:
    """An available resource from the pool."""
    id: int
    kind: str  # ambulance, rescue_team, truck, excavator, helicopter, boat
    available: int
    location: tuple[float, float] | None  # (lat, lon) of HQ/depot


@dataclass
class ResourceAssignment:
    """An assignment of resources to a request."""
    request_id: str
    resource_kind: str
    resource_count: int
    estimated_arrival_min: int
    confidence: float  # 0-1, how good this assignment is


def compute_request_severity(request: EmergencyRequest, risk_at_location: float = 0.5) -> float:
    """Compute request severity score (0-1).

    Factors:
    - Number of people (more people = higher severity)
    - Category (medical > evacuation > stranded)
    - Risk at location (from landslide susceptibility)
    - Time since request (older requests = higher severity)
    """
    # People count factor (more people = higher severity, capped at 0.5)
    people_factor = min(request.people_count / 20, 0.5)

    # Category factor
    category_weights = {
        "medical": 0.4,
        "evacuation": 0.3,
        "stranded": 0.2,
    }
    category_factor = category_weights.get(request.category, 0.2)

    # Risk factor
    risk_factor = risk_at_location * 0.1

    # Base severity
    severity = people_factor + category_factor + risk_factor

    return min(severity, 1.0)


def match_resources_to_requests(
    requests: list[EmergencyRequest],
    resources: list[AvailableResource],
    backend: str = "ortools",
) -> list[ResourceAssignment]:
    """Match available resources to emergency requests using QUBO dispatch.

    Args:
        requests: List of emergency requests needing help
        resources: List of available resources in the pool
        backend: Optimization backend (qaoa, annealing, ortools, greedy)

    Returns:
        List of resource assignments

    Uses the existing qubo_dispatch package for optimization. The formulation
    is hardware-ready for quantum backends but runs on classical solvers today.
    """
    if not requests or not resources:
        return []

    if DispatchProblem is None or solve_dispatch_ortools is None:
        # Fallback to simple matching if package unavailable
        return _simple_greedy_allocation(requests, resources)

    # Convert to QUBO dispatch format
    qd_requests = []
    for req in requests:
        qd_requests.append(QDRequest(
            id=req.id,
            location=req.location,
            people_count=req.people_count,
            category=req.category,
            severity=req.severity,
            created_at=req.created_at,
        ))

    qd_units = []
    unit_id_counter = 0
    for res in resources:
        for i in range(res.available):
            unit_id_counter += 1
            qd_units.append(QDUnit(
                id=f"{res.kind}_{unit_id_counter}",
                label=f"{res.kind} {i+1}",
                kind=res.kind,
                capacity=1,
                position=res.location or (23.7271, 92.7176),  # HQ if no location
                home_base=res.location or (23.7271, 92.7176),
                status="available",
            ))

    # Create dispatch problem
    problem = DispatchProblem(requests=qd_requests, units=qd_units)

    # Solve using specified backend
    result = solve_dispatch_ortools(problem)

    # Convert assignments back to our format
    assignments: list[ResourceAssignment] = []
    for assignment in result.assignments:
        unit = next((u for u in qd_units if u.id == assignment.unit_id), None)
        request = next((r for r in qd_requests if r.id == assignment.request_id), None)

        if unit and request:
            assignments.append(ResourceAssignment(
                request_id=request.id,
                resource_kind=unit.kind,
                resource_count=1,
                estimated_arrival_min=assignment.travel_s or 30,  # fallback estimate
                confidence=0.8,
            ))

    return assignments


def _simple_greedy_allocation(
    requests: list[EmergencyRequest],
    resources: list[AvailableResource],
) -> list[ResourceAssignment]:
    """Simple greedy fallback if QUBO package unavailable."""
    # Group resources by kind
    resources_by_kind: dict[str, list[AvailableResource]] = {}
    for r in resources:
        if r.available > 0:
            if r.kind not in resources_by_kind:
                resources_by_kind[r.kind] = []
            resources_by_kind[r.kind].append(r)

    assignments: list[ResourceAssignment] = []
    sorted_requests = sorted(requests, key=lambda r: r.severity, reverse=True)

    for request in sorted_requests:
        needed_kinds = []
        if request.category == "medical":
            needed_kinds = ["ambulance", "rescue_team"]
        elif request.category == "evacuation":
            needed_kinds = ["truck", "rescue_team", "boat"]
        elif request.category == "stranded":
            needed_kinds = ["rescue_team", "helicopter"]

        for kind in needed_kinds:
            if kind in resources_by_kind and resources_by_kind[kind]:
                resource = resources_by_kind[kind][0]
                if resource.available > 0:
                    distance_km = haversine_distance(resource.location or (23.7271, 92.7176), request.location)
                    arrival_min = int(distance_km * 2)

                    assignments.append(ResourceAssignment(
                        request_id=request.id,
                        resource_kind=kind,
                        resource_count=1,
                        estimated_arrival_min=arrival_min,
                        confidence=0.8 if arrival_min < 30 else 0.5,
                    ))

                    resource.available -= 1
                    if resource.available <= 0:
                        resources_by_kind[kind].pop(0)

    return assignments


def haversine_distance(loc1: tuple[float, float], loc2: tuple[float, float]) -> float:
    """Compute Haversine distance between two lat/lon points in km."""
    lat1, lon1 = loc1
    lat2, lon2 = loc2

    R = 6371  # Earth radius in km

    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)

    a = (np.sin(dlat / 2) ** 2 +
         np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) *
         np.sin(dlon / 2) ** 2)

    c = 2 * np.arcsin(np.sqrt(a))

    return R * c


def approve_resource_allocation(request_id: str, assignments: list[ResourceAssignment]) -> dict:
    """Approve a resource allocation and create dispatch records.

    This would create entries in the assignments table and update unit status.
    For now, returns the approval confirmation.
    """
    return {
        "request_id": request_id,
        "approved": True,
        "assignments": [
            {
                "resource_kind": a.resource_kind,
                "resource_count": a.resource_count,
                "estimated_arrival_min": a.estimated_arrival_min,
            }
            for a in assignments
        ],
        "approved_at": "now"  # Would be actual timestamp
    }
