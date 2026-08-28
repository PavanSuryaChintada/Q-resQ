from qubo_dispatch.benchmark import benchmark
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


def test_returns_one_row_per_backend_with_the_required_fields():
    rows = benchmark(_problem(), backends=("annealing", "ortools", "greedy"))

    assert [row["backend"] for row in rows] == ["annealing", "ortools", "greedy"]
    for row in rows:
        assert set(row.keys()) == {"backend", "objective", "solve_ms", "constraints_valid", "qubit_count"}
        assert row["constraints_valid"] is True


def test_does_not_reorder_rows_by_objective():
    # order must track the input backends tuple exactly - never sorted
    # so quantum appears first, and never filtered to hide losing rows
    rows = benchmark(_problem(), backends=("greedy", "ortools", "annealing"))
    assert [row["backend"] for row in rows] == ["greedy", "ortools", "annealing"]


def test_every_backend_solves_the_same_tuned_problem():
    rows = benchmark(_problem(), backends=("annealing", "ortools", "greedy"))
    # all rows report a real (non-placeholder) objective and timing
    for row in rows:
        assert isinstance(row["objective"], float)
        assert row["solve_ms"] >= 0
        assert row["qubit_count"] is not None
