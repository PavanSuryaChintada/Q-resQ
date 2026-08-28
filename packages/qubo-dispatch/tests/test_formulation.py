import itertools

import pytest

from qubo_dispatch.formulation import build_qubo, evaluate
from qubo_dispatch.types import DispatchProblem, QUBO, Request, Unit


def _problem(travel_time_s, alpha=0.3):
    return DispatchProblem(
        units=[Unit(id="u1", capacity=1, position=(0.0, 0.0)),
               Unit(id="u2", capacity=1, position=(0.0, 0.0))],
        requests=[Request(id="r1", severity=0.5, people=2, position=(0.0, 0.0)),
                  Request(id="r2", severity=0.8, people=4, position=(0.0, 0.0))],
        travel_time_s=travel_time_s,
        alpha=alpha,
    )


def test_creates_one_variable_per_reachable_pair_only():
    problem = _problem({
        ("u1", "r1"): 100.0,
        ("u1", "r2"): 200.0,
        ("u2", "r1"): 150.0,
        # u2 cannot reach r2 - every road flooded, no key at all
    })

    qubo = build_qubo(problem, lam=1.0)

    assert qubo.n_vars == 3
    assert set(qubo.index.keys()) == {("u1", "r1"), ("u1", "r2"), ("u2", "r1")}
    assert ("u2", "r2") not in qubo.index


def test_diagonal_reflects_normalised_value_minus_alpha_travel():
    # r1: severity*people = 0.5*2 = 1.0, r2: 0.8*4 = 3.2 (max_value)
    # travel: (u1,r1)=100, (u1,r2)=200 (max_travel)
    problem = _problem({("u1", "r1"): 100.0, ("u1", "r2"): 200.0}, alpha=0.3)

    qubo = build_qubo(problem, lam=1.0)

    k_r1 = qubo.index[("u1", "r1")]
    k_r2 = qubo.index[("u1", "r2")]

    value_norm_r1, travel_norm_r1 = 1.0 / 3.2, 100.0 / 200.0
    value_norm_r2, travel_norm_r2 = 3.2 / 3.2, 200.0 / 200.0

    assert qubo.Q[(k_r1, k_r1)] == pytest.approx(-value_norm_r1 + 0.3 * travel_norm_r1)
    assert qubo.Q[(k_r2, k_r2)] == pytest.approx(-value_norm_r2 + 0.3 * travel_norm_r2)


def test_zero_severity_and_zero_travel_do_not_produce_nan():
    problem = DispatchProblem(
        units=[Unit(id="u1", capacity=1, position=(0.0, 0.0))],
        requests=[Request(id="r1", severity=0.0, people=1, position=(0.0, 0.0))],
        travel_time_s={("u1", "r1"): 0.0},
    )

    qubo = build_qubo(problem, lam=1.0)

    k = qubo.index[("u1", "r1")]
    assert qubo.Q[(k, k)] == 0.0


def test_at_most_one_pairwise_penalties_are_upper_triangular_with_factor_two():
    # fully connected: 2 units x 2 requests, all four pairs reachable
    problem = _problem({
        ("u1", "r1"): 100.0, ("u1", "r2"): 200.0,
        ("u2", "r1"): 150.0, ("u2", "r2"): 250.0,
    })

    qubo = build_qubo(problem, lam=2.0)

    k_u1r1 = qubo.index[("u1", "r1")]
    k_u1r2 = qubo.index[("u1", "r2")]
    k_u2r1 = qubo.index[("u2", "r1")]
    k_u2r2 = qubo.index[("u2", "r2")]

    def pair(a, b):
        return (min(a, b), max(a, b))

    # at-most-one unit per request r1: u1 vs u2
    assert qubo.Q[pair(k_u1r1, k_u2r1)] == pytest.approx(4.0)
    # at-most-one unit per request r2: u1 vs u2
    assert qubo.Q[pair(k_u1r2, k_u2r2)] == pytest.approx(4.0)
    # at-most-one request per unit u1: r1 vs r2
    assert qubo.Q[pair(k_u1r1, k_u1r2)] == pytest.approx(4.0)
    # at-most-one request per unit u2: r1 vs r2
    assert qubo.Q[pair(k_u2r1, k_u2r2)] == pytest.approx(4.0)

    # no cross term between unrelated pairs (different unit AND different request)
    assert pair(k_u1r1, k_u2r2) not in qubo.Q
    assert pair(k_u1r2, k_u2r1) not in qubo.Q

    # every stored key is already (min, max) - strictly upper triangular
    for (a, b) in qubo.Q:
        assert a <= b


def test_evaluate_sums_quadratic_terms_plus_offset():
    qubo = QUBO(
        Q={(0, 0): -1.0, (1, 1): 2.0, (0, 1): 3.0},
        n_vars=2,
        index={},
        reverse={},
        offset=0.5,
    )

    assert evaluate(qubo, {0: 1, 1: 1}) == pytest.approx(-1.0 + 2.0 + 3.0 + 0.5)
    assert evaluate(qubo, {0: 1, 1: 0}) == pytest.approx(-1.0 + 0.5)
    assert evaluate(qubo, {0: 0, 1: 0}) == pytest.approx(0.5)


def test_qubo_minimum_matches_brute_force_optimum_and_is_feasible():
    # small enough to brute-force: 2 units x 3 requests, fully connected
    problem = DispatchProblem(
        units=[Unit(id="u1", capacity=1, position=(0.0, 0.0)),
               Unit(id="u2", capacity=1, position=(0.0, 0.0))],
        requests=[Request(id="r1", severity=0.9, people=5, position=(0.0, 0.0)),
                  Request(id="r2", severity=0.4, people=2, position=(0.0, 0.0)),
                  Request(id="r3", severity=0.6, people=3, position=(0.0, 0.0))],
        travel_time_s={
            ("u1", "r1"): 300.0, ("u1", "r2"): 100.0, ("u1", "r3"): 500.0,
            ("u2", "r1"): 200.0, ("u2", "r2"): 400.0, ("u2", "r3"): 150.0,
        },
        alpha=0.3,
    )
    lam = 1.2 * (1.0 + problem.alpha)
    qubo = build_qubo(problem, lam=lam)

    def is_feasible(assignment: dict[int, int]) -> bool:
        chosen = [qubo.reverse[k] for k, v in assignment.items() if v == 1]
        units_used = [u for u, _ in chosen]
        requests_used = [r for _, r in chosen]
        return len(units_used) == len(set(units_used)) and len(requests_used) == len(set(requests_used))

    best_feasible = None
    best_feasible_energy = None
    best_overall_energy = None
    for bits in itertools.product([0, 1], repeat=qubo.n_vars):
        assignment = dict(enumerate(bits))
        energy = evaluate(qubo, assignment)
        if best_overall_energy is None or energy < best_overall_energy:
            best_overall_energy = energy
        if is_feasible(assignment):
            if best_feasible_energy is None or energy < best_feasible_energy:
                best_feasible_energy = energy
                best_feasible = assignment

    # the global minimum of the QUBO must itself be a feasible assignment
    assert best_overall_energy == pytest.approx(best_feasible_energy)
    assert is_feasible(best_feasible)
