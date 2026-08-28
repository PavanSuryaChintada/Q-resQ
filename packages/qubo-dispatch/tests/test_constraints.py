"""RELEASE GATE: across random instances, no solver ever double-books
a unit or a request. Extended with each solver as it's built.
"""

import random

import pytest

from qubo_dispatch.formulation import build_qubo
from qubo_dispatch.penalties import tune_penalty
from qubo_dispatch.solvers.base import validate_constraints
from qubo_dispatch.solvers.greedy import GreedySolver
from qubo_dispatch.types import DispatchProblem, Request, Unit


def _random_problem(rng: random.Random) -> DispatchProblem:
    n_units = rng.randint(2, 5)
    n_requests = rng.randint(3, 8)
    units = [Unit(id=f"u{i}", capacity=rng.randint(1, 6), position=(rng.uniform(-1, 1), rng.uniform(-1, 1)))
             for i in range(n_units)]
    requests = [Request(id=f"r{j}", severity=rng.uniform(0, 1), people=rng.randint(1, 10),
                         position=(rng.uniform(-1, 1), rng.uniform(-1, 1)))
                for j in range(n_requests)]
    travel_time_s = {}
    for u in units:
        for r in requests:
            if rng.random() < 0.85:  # occasionally unreachable, like a flooded road
                travel_time_s[(u.id, r.id)] = rng.uniform(30, 3600)
    return DispatchProblem(units=units, requests=requests, travel_time_s=travel_time_s)


def _solvers():
    # qaoa is deliberately excluded from this 500-instance sweep: each
    # call pays real Aer transpile + circuit-simulation cost, which
    # turns this from a seconds-long property test into a run measured
    # in hours for no extra correctness signal. Its own feasibility,
    # sign-convention, and qubit-guard behaviour is covered by
    # test_solvers_qaoa.py, and its fallback behaviour by
    # test_fallback.py - both far cheaper ways to exercise the same
    # validate_constraints gate.
    solvers = [GreedySolver()]
    try:
        from qubo_dispatch.solvers.annealing import AnnealingSolver
        solvers.append(AnnealingSolver())
    except ImportError:
        pass
    try:
        import ortools  # noqa: F401 - the real dependency check; ortools_solver.py
        # imports it lazily inside solve(), so importing the wrapper
        # module alone would never detect it's missing
        from qubo_dispatch.solvers.ortools_solver import OrtoolsSolver
        solvers.append(OrtoolsSolver())
    except ImportError:
        pass
    return solvers


@pytest.mark.parametrize("seed", range(500))
def test_no_solver_ever_double_books_across_random_instances(seed):
    rng = random.Random(seed)
    problem = _random_problem(rng)
    if not problem.travel_time_s:
        return  # degenerate instance, nothing reachable - not what we're testing here
    lam = tune_penalty(problem)
    qubo = build_qubo(problem, lam=lam)

    for solver in _solvers():
        result = solver.solve(qubo, problem, timeout_s=10.0)
        assert validate_constraints(result.assignments), (
            f"{solver.name} double-booked on seed {seed}: {result.assignments}"
        )
