"""Run the same tuned QUBO through every backend. See BUILD_SPEC.md §11.

Do not sort so quantum appears first. Do not filter losing rows. A
table where QAOA wins every row reads as fabricated - honest parity
reads as engineering, and it pre-empts the hostile question.
"""

from __future__ import annotations

from qubo_dispatch.formulation import build_qubo
from qubo_dispatch.penalties import tune_penalty
from qubo_dispatch.router import _get_solver
from qubo_dispatch.solvers.base import validate_constraints
from qubo_dispatch.types import DispatchProblem


def benchmark(
    problem: DispatchProblem,
    backends: tuple[str, ...] = ("qaoa", "annealing", "ortools", "greedy"),
    timeout_s: float = 10.0,
) -> list[dict]:
    lam = tune_penalty(problem)
    qubo = build_qubo(problem, lam=lam)

    rows = []
    for backend in backends:
        solver = _get_solver(backend)
        result = solver.solve(qubo, problem, timeout_s)
        rows.append({
            "backend": backend,
            "objective": result.objective,
            "solve_ms": result.solve_ms,
            "constraints_valid": validate_constraints(result.assignments),
            "qubit_count": result.qubit_count,
        })
    return rows
