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
        try:
            solver = _get_solver(backend)
            result = solver.solve(qubo, problem, timeout_s)
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # noqa: BLE001 - a backend that can't run at this size is a
            # result to report, not a crash. validate_constraints never
            # runs on a result that doesn't exist, so this row is
            # explicitly invalid rather than silently omitted.
            rows.append({
                "backend": backend, "objective": None, "solve_ms": None,
                "constraints_valid": False, "qubit_count": qubo.n_vars,
                "notes": str(exc),
            })
            continue
        rows.append({
            "backend": backend,
            "objective": result.objective,
            "solve_ms": result.solve_ms,
            "constraints_valid": validate_constraints(result.assignments),
            "qubit_count": result.qubit_count,
            "notes": None,
        })
    return rows
