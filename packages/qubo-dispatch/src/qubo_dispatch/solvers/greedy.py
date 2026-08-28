"""Severity-descending, nearest-available-unit greedy solver. See BUILD_SPEC.md §5.

stdlib only. This is the floor of the fallback chain and must be
incapable of failing.
"""

from __future__ import annotations

import time

from qubo_dispatch.formulation import evaluate
from qubo_dispatch.types import DispatchProblem, DispatchResult, QUBO


def greedy_bitstring(qubo: QUBO, problem: DispatchProblem) -> dict[int, int]:
    x = {k: 0 for k in range(qubo.n_vars)}
    used_units: set[str] = set()

    requests_sorted = sorted(problem.requests, key=lambda r: -(r.severity * r.people))
    for request in requests_sorted:
        candidates = sorted(
            (problem.travel_time_s[(u.id, request.id)], u.id)
            for u in problem.units
            if u.id not in used_units and (u.id, request.id) in problem.travel_time_s
        )
        if not candidates:
            continue
        _, unit_id = candidates[0]
        used_units.add(unit_id)
        pair = (unit_id, request.id)
        if pair in qubo.index:
            x[qubo.index[pair]] = 1

    return x


class GreedySolver:
    name = "greedy"

    def solve(self, qubo: QUBO, problem: DispatchProblem, timeout_s: float) -> DispatchResult:
        start = time.monotonic()
        x = greedy_bitstring(qubo, problem)
        assignments = [qubo.reverse[k] for k, v in x.items() if v == 1]
        objective = evaluate(qubo, x)
        solve_ms = int((time.monotonic() - start) * 1000)
        return DispatchResult(
            assignments=assignments,
            objective=objective,
            backend=self.name,
            fell_back=False,
            solve_ms=solve_ms,
            qubit_count=qubo.n_vars,
        )
