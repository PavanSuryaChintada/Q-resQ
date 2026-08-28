"""Constrained k-means zoning and parallel per-zone solving. See BUILD_SPEC.md §9.

Scaling is horizontal: the QUBO never grows, zones do. A unit near a
zone boundary may be better used in the neighbouring zone - boundary
suboptimality is traded for constant-size subproblems, and
re-partitioning every round prevents the error accumulating.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

from qubo_dispatch.router import solve
from qubo_dispatch.solvers.base import validate_constraints
from qubo_dispatch.types import DispatchProblem, DispatchResult, Request, Unit


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    n = len(points)
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)


def _cluster_requests(requests: list[Request], k: int) -> dict[int, list[Request]]:
    from sklearn.cluster import KMeans

    coords = [[r.position[0], r.position[1]] for r in requests]
    labels = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(coords)

    clusters: dict[int, list[Request]] = defaultdict(list)
    for request, label in zip(requests, labels):
        clusters[int(label)].append(request)
    return clusters


def _enforce_request_cap(clusters: dict[int, list[Request]], max_requests_per_zone: int) -> None:
    changed = True
    while changed:
        changed = False
        for cid in list(clusters.keys()):
            while len(clusters[cid]) > max_requests_per_zone:
                centroid = _centroid([r.position for r in clusters[cid]])
                farthest = max(clusters[cid], key=lambda r: _distance(r.position, centroid))

                candidates = [
                    (other, _distance(farthest.position, _centroid([r.position for r in clusters[other]])))
                    for other in clusters
                    if other != cid and len(clusters[other]) < max_requests_per_zone
                ]
                if not candidates:
                    break  # no room anywhere - every zone already at cap
                target, _ = min(candidates, key=lambda pair: pair[1])

                clusters[cid].remove(farthest)
                clusters[target].append(farthest)
                changed = True


def partition(
    problem: DispatchProblem,
    max_requests_per_zone: int = 5,
    max_units_per_zone: int = 4,
) -> list[DispatchProblem]:
    if not problem.requests:
        return []

    k = min(math.ceil(len(problem.requests) / max_requests_per_zone), len(problem.requests))
    clusters = _cluster_requests(problem.requests, k)
    _enforce_request_cap(clusters, max_requests_per_zone)

    zone_request_lists = [members for members in clusters.values() if members]
    # assign units in order of zone severity total, highest first
    zone_request_lists.sort(
        key=lambda members: sum(r.severity * r.people for r in members), reverse=True
    )

    zones: list[DispatchProblem] = []
    used_unit_ids: set[str] = set()
    for members in zone_request_lists:
        zone_centroid = _centroid([r.position for r in members])
        available = [u for u in problem.units if u.id not in used_unit_ids]
        available.sort(key=lambda u: _distance(u.position, zone_centroid))
        zone_units = available[:max_units_per_zone]
        used_unit_ids.update(u.id for u in zone_units)

        zone_unit_ids = {u.id for u in zone_units}
        zone_request_ids = {r.id for r in members}
        zone_travel = {
            pair: t for pair, t in problem.travel_time_s.items()
            if pair[0] in zone_unit_ids and pair[1] in zone_request_ids
        }
        zones.append(DispatchProblem(
            units=zone_units, requests=members, travel_time_s=zone_travel, alpha=problem.alpha,
        ))

    return zones


def solve_partitioned(
    problem: DispatchProblem,
    backend: str = "qaoa",
    timeout_s: float = 10.0,
    max_requests_per_zone: int = 5,
    max_units_per_zone: int = 4,
    max_workers: int | None = None,
) -> DispatchResult:
    start = time.monotonic()
    zones = partition(problem, max_requests_per_zone, max_units_per_zone)
    zones_to_solve = [zone for zone in zones if zone.units]  # empty-unit zones crash some solvers

    if not zones_to_solve:
        return DispatchResult(assignments=[], objective=0.0, backend=backend, fell_back=False, solve_ms=0, qubit_count=0)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(solve, zone, backend, timeout_s) for zone in zones_to_solve]
        results = [future.result() for future in futures]

    assignments = [pair for result in results for pair in result.assignments]
    objective = sum(result.objective for result in results)
    fell_back = any(result.fell_back for result in results)
    backends_used = {result.backend for result in results}
    qubit_count = max((result.qubit_count or 0) for result in results)
    solve_ms = int((time.monotonic() - start) * 1000)

    merged = DispatchResult(
        assignments=assignments,
        objective=objective,
        backend=backends_used.pop() if len(backends_used) == 1 else "mixed",
        fell_back=fell_back,
        solve_ms=solve_ms,
        qubit_count=qubit_count,
    )

    # per-zone validity does not guarantee global validity if the unit
    # assignment step has a bug - check the merged result too
    if not validate_constraints(merged.assignments):
        raise RuntimeError("solve_partitioned produced a double-booking across zones - this is a bug")

    return merged
