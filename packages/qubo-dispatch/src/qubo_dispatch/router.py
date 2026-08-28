"""solve(problem, backend=...) with the hard fallback chain. See BUILD_SPEC.md §8.

qaoa -> (timeout / exception) -> annealing -> greedy. Quantum is never
in the critical path: if greedy also fails, that's a genuine bug.
"""

from __future__ import annotations

import logging

from qubo_dispatch.formulation import build_qubo
from qubo_dispatch.penalties import tune_penalty
from qubo_dispatch.solvers.base import Solver, validate_constraints
from qubo_dispatch.types import DispatchProblem, DispatchResult

logger = logging.getLogger(__name__)

FALLBACK_CHAINS: dict[str, list[str]] = {
    "qaoa": ["qaoa", "annealing", "greedy"],
    "annealing": ["annealing", "greedy"],
    "ortools": ["ortools", "greedy"],
    "greedy": ["greedy"],
}


def _get_solver(name: str) -> Solver:
    if name == "qaoa":
        from qubo_dispatch.solvers.qaoa import QaoaSolver

        return QaoaSolver()
    if name == "annealing":
        from qubo_dispatch.solvers.annealing import AnnealingSolver

        return AnnealingSolver()
    if name == "ortools":
        from qubo_dispatch.solvers.ortools_solver import OrtoolsSolver

        return OrtoolsSolver()
    if name == "greedy":
        from qubo_dispatch.solvers.greedy import GreedySolver

        return GreedySolver()
    raise ValueError(f"unknown backend: {name}")


def solve(problem: DispatchProblem, backend: str = "qaoa", timeout_s: float = 10.0) -> DispatchResult:
    chain = FALLBACK_CHAINS[backend]
    lam = tune_penalty(problem)
    qubo = build_qubo(problem, lam=lam)

    for position, name in enumerate(chain):
        try:
            solver = _get_solver(name)
            result = solver.solve(qubo, problem, timeout_s)
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # noqa: BLE001 - catch everything except KeyboardInterrupt, log and fall through
            logger.warning("solver %s failed, falling through: %s", name, exc)
            continue

        if validate_constraints(result.assignments):
            result.backend = name
            result.fell_back = position != 0
            return result

        logger.warning("solver %s returned an invalid assignment, falling through", name)

    raise RuntimeError("greedy failed - this is a bug, greedy cannot fail")
