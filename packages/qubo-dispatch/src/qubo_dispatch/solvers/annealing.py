"""Simulated annealing on the QUBO. See BUILD_SPEC.md §6. Pure Python."""

from __future__ import annotations

import math
import random
import time

from qubo_dispatch.formulation import evaluate
from qubo_dispatch.solvers.base import validate_constraints
from qubo_dispatch.solvers.greedy import greedy_bitstring
from qubo_dispatch.types import DispatchProblem, DispatchResult, QUBO


def _build_neighbors(qubo: QUBO) -> tuple[dict[int, float], dict[int, list[tuple[int, float]]]]:
    diag: dict[int, float] = {}
    adj: dict[int, list[tuple[int, float]]] = {k: [] for k in range(qubo.n_vars)}
    for (i, j), coeff in qubo.Q.items():
        if i == j:
            diag[i] = coeff
        else:
            adj[i].append((j, coeff))
            adj[j].append((i, coeff))
    return diag, adj


def _flip_delta(k: int, x: dict[int, int], diag: dict[int, float],
                 adj: dict[int, list[tuple[int, float]]]) -> float:
    old = x[k]
    new = 1 - old
    step = new - old
    delta = step * diag.get(k, 0.0)
    for j, coeff in adj[k]:
        delta += step * coeff * x[j]
    return delta


def _feasible_assignments(qubo: QUBO, x: dict[int, int]) -> list[tuple[str, str]]:
    return [qubo.reverse[k] for k, v in x.items() if v == 1]


class AnnealingSolver:
    name = "annealing"

    def solve(self, qubo: QUBO, problem: DispatchProblem, timeout_s: float) -> DispatchResult:
        start = time.monotonic()
        rng = random.Random()

        x = greedy_bitstring(qubo, problem)
        diag, adj = _build_neighbors(qubo)
        energy = evaluate(qubo, x)

        best_x = dict(x)
        best_energy = energy if validate_constraints(_feasible_assignments(qubo, x)) else None

        T0 = qubo.lam if qubo.lam else 1.0
        max_steps = max(200, 50 * max(qubo.n_vars, 1))

        step = 0
        while step < max_steps:
            if step % 100 == 0 and time.monotonic() - start > timeout_s:
                break

            k = rng.randrange(qubo.n_vars) if qubo.n_vars else 0
            if qubo.n_vars == 0:
                break
            delta = _flip_delta(k, x, diag, adj)
            T = T0 * (0.95 ** step)
            if delta <= 0 or rng.random() < math.exp(-delta / T if T > 0 else float("-inf")):
                x[k] = 1 - x[k]
                energy += delta
                assignments = _feasible_assignments(qubo, x)
                if validate_constraints(assignments) and (best_energy is None or energy < best_energy):
                    best_energy = energy
                    best_x = dict(x)

            step += 1

        assignments = _feasible_assignments(qubo, best_x)
        objective = evaluate(qubo, best_x)
        solve_ms = int((time.monotonic() - start) * 1000)
        return DispatchResult(
            assignments=assignments,
            objective=objective,
            backend=self.name,
            fell_back=False,
            solve_ms=solve_ms,
            qubit_count=qubo.n_vars,
        )
