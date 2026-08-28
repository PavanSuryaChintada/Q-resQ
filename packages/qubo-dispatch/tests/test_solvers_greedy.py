from qubo_dispatch.formulation import build_qubo
from qubo_dispatch.solvers.base import validate_constraints
from qubo_dispatch.solvers.greedy import GreedySolver, greedy_bitstring
from qubo_dispatch.types import DispatchProblem, Request, Unit


def test_assigns_highest_value_request_to_its_nearest_reachable_unit():
    problem = DispatchProblem(
        units=[Unit(id="u1", capacity=1, position=(0.0, 0.0)),
               Unit(id="u2", capacity=1, position=(0.0, 0.0))],
        requests=[Request(id="r1", severity=0.9, people=5, position=(0.0, 0.0)),
                  Request(id="r2", severity=0.1, people=1, position=(0.0, 0.0))],
        travel_time_s={
            ("u1", "r1"): 500.0, ("u2", "r1"): 100.0,  # u2 is nearer to r1
            ("u1", "r2"): 300.0, ("u2", "r2"): 400.0,
        },
    )
    qubo = build_qubo(problem, lam=1.0)

    x = greedy_bitstring(qubo, problem)
    chosen = {qubo.reverse[k] for k, v in x.items() if v == 1}

    assert ("u2", "r1") in chosen  # highest-value request went to its nearest unit
    assert ("u1", "r2") in chosen  # only unit left for r2


def test_skips_a_request_with_no_reachable_unit():
    problem = DispatchProblem(
        units=[Unit(id="u1", capacity=1, position=(0.0, 0.0))],
        requests=[Request(id="r1", severity=0.9, people=5, position=(0.0, 0.0)),
                  Request(id="r2", severity=0.1, people=1, position=(0.0, 0.0))],
        travel_time_s={("u1", "r1"): 100.0},  # r2 unreachable by anyone
    )
    qubo = build_qubo(problem, lam=1.0)

    x = greedy_bitstring(qubo, problem)
    chosen = {qubo.reverse[k] for k, v in x.items() if v == 1}

    assert chosen == {("u1", "r1")}


def test_solve_returns_a_valid_dispatch_result():
    problem = DispatchProblem(
        units=[Unit(id="u1", capacity=1, position=(0.0, 0.0)),
               Unit(id="u2", capacity=1, position=(0.0, 0.0))],
        requests=[Request(id="r1", severity=0.9, people=5, position=(0.0, 0.0)),
                  Request(id="r2", severity=0.4, people=2, position=(0.0, 0.0))],
        travel_time_s={
            ("u1", "r1"): 300.0, ("u2", "r1"): 100.0,
            ("u1", "r2"): 200.0, ("u2", "r2"): 400.0,
        },
    )
    qubo = build_qubo(problem, lam=1.0)

    result = GreedySolver().solve(qubo, problem, timeout_s=10.0)

    assert result.backend == "greedy"
    assert result.fell_back is False
    assert validate_constraints(result.assignments) is True
    assert result.solve_ms >= 0
