import random

import pytest

from qubo_dispatch.penalties import tune_penalty
from qubo_dispatch.types import DispatchProblem, Request, Unit


def _problem(alpha=0.3):
    return DispatchProblem(
        units=[Unit(id="u1", capacity=1, position=(0.0, 0.0))],
        requests=[Request(id="r1", severity=0.5, people=2, position=(0.0, 0.0))],
        travel_time_s={("u1", "r1"): 100.0},
        alpha=alpha,
    )


def test_default_margin_is_1_2x_the_bound():
    problem = _problem(alpha=0.3)
    assert tune_penalty(problem) == pytest.approx(1.2 * (1.0 + 0.3))


def test_custom_margin_scales_the_bound():
    problem = _problem(alpha=0.3)
    assert tune_penalty(problem, margin=2.0) == pytest.approx(2.0 * (1.0 + 0.3))


@pytest.mark.parametrize("alpha", [0.0, 0.1, 0.3, 0.5, 1.0])
def test_penalty_always_exceeds_the_bound(alpha):
    # since both objective terms are normalised to [0,1], the maximum
    # possible objective gain from breaking a constraint is bounded by
    # 1.0 + alpha; the tuned penalty must exceed that bound
    problem = _problem(alpha=alpha)
    bound = 1.0 + alpha
    assert tune_penalty(problem) > bound


def test_penalty_exceeds_bound_across_random_alphas():
    rng = random.Random(42)
    for _ in range(100):
        alpha = rng.uniform(0.0, 2.0)
        problem = _problem(alpha=alpha)
        bound = 1.0 + alpha
        assert tune_penalty(problem) > bound
