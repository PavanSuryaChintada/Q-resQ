from qubo_dispatch.formulation import build_qubo
from qubo_dispatch.solvers.base import validate_constraints
from qubo_dispatch.solvers.greedy import GreedySolver
from qubo_dispatch.solvers.ortools_solver import OrtoolsSolver
from qubo_dispatch.types import DispatchProblem, Request, Unit


def _problem():
    return DispatchProblem(
        units=[Unit(id="u1", capacity=1, position=(0.0, 0.0)),
               Unit(id="u2", capacity=1, position=(0.0, 0.0)),
               Unit(id="u3", capacity=1, position=(0.0, 0.0))],
        requests=[Request(id="r1", severity=0.9, people=5, position=(0.0, 0.0)),
                  Request(id="r2", severity=0.4, people=2, position=(0.0, 0.0)),
                  Request(id="r3", severity=0.6, people=3, position=(0.0, 0.0)),
                  Request(id="r4", severity=0.2, people=1, position=(0.0, 0.0))],
        travel_time_s={
            ("u1", "r1"): 300.0, ("u1", "r2"): 100.0, ("u1", "r3"): 500.0, ("u1", "r4"): 250.0,
            ("u2", "r1"): 200.0, ("u2", "r2"): 400.0, ("u2", "r3"): 150.0, ("u2", "r4"): 600.0,
            ("u3", "r1"): 350.0, ("u3", "r2"): 120.0, ("u3", "r3"): 220.0, ("u3", "r4"): 90.0,
        },
    )


def test_returns_a_feasible_assignment():
    problem = _problem()
    qubo = build_qubo(problem, lam=1.5)

    result = OrtoolsSolver().solve(qubo, problem, timeout_s=5.0)

    assert validate_constraints(result.assignments) is True
    assert result.backend == "ortools"
    assert result.fell_back is False


def test_is_the_honest_production_baseline_never_worse_than_greedy():
    problem = _problem()
    qubo = build_qubo(problem, lam=1.5)

    greedy_result = GreedySolver().solve(qubo, problem, timeout_s=5.0)
    ortools_result = OrtoolsSolver().solve(qubo, problem, timeout_s=5.0)

    assert ortools_result.objective <= greedy_result.objective + 1e-9


def test_objective_reported_through_shared_evaluate_not_cpsat_internal():
    from qubo_dispatch.formulation import evaluate

    problem = _problem()
    qubo = build_qubo(problem, lam=1.5)
    result = OrtoolsSolver().solve(qubo, problem, timeout_s=5.0)

    x = {k: 0 for k in range(qubo.n_vars)}
    for pair in result.assignments:
        x[qubo.index[pair]] = 1

    assert result.objective == evaluate(qubo, x)
