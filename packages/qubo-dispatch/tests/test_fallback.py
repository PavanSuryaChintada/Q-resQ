"""RELEASE GATE: solve() must always return a valid assignment, even
when the requested backend is unavailable or fails.
"""

from qubo_dispatch.router import solve
from qubo_dispatch.solvers.base import validate_constraints
from qubo_dispatch.types import DispatchProblem, Request, Unit


def _problem():
    return DispatchProblem(
        units=[Unit(id="u1", capacity=1, position=(0.0, 0.0)),
               Unit(id="u2", capacity=1, position=(0.0, 0.0))],
        requests=[Request(id="r1", severity=0.9, people=5, position=(0.0, 0.0)),
                  Request(id="r2", severity=0.4, people=2, position=(0.0, 0.0))],
        travel_time_s={
            ("u1", "r1"): 300.0, ("u1", "r2"): 100.0,
            ("u2", "r1"): 200.0, ("u2", "r2"): 400.0,
        },
    )


def test_greedy_backend_always_succeeds():
    result = solve(_problem(), backend="greedy", timeout_s=5.0)
    assert validate_constraints(result.assignments) is True
    assert result.backend == "greedy"
    assert result.fell_back is False


def test_ortools_backend_succeeds_without_falling_back():
    result = solve(_problem(), backend="ortools", timeout_s=5.0)
    assert validate_constraints(result.assignments) is True
    assert result.backend == "ortools"
    assert result.fell_back is False


def test_annealing_backend_succeeds_without_falling_back():
    result = solve(_problem(), backend="annealing", timeout_s=5.0)
    assert validate_constraints(result.assignments) is True
    assert result.backend == "annealing"
    assert result.fell_back is False


def test_qaoa_backend_succeeds_without_falling_back_when_available():
    result = solve(_problem(), backend="qaoa", timeout_s=5.0)
    assert validate_constraints(result.assignments) is True
    assert result.fell_back is False
    assert result.backend == "qaoa"


def test_unknown_backend_raises():
    import pytest
    with pytest.raises(KeyError):
        solve(_problem(), backend="not-a-real-backend", timeout_s=5.0)


def test_qaoa_falls_back_when_qiskit_import_itself_raises(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "qiskit" or name.startswith("qiskit."):
            raise ImportError("qiskit monkeypatched to fail for this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = solve(_problem(), backend="qaoa", timeout_s=5.0)

    assert validate_constraints(result.assignments) is True
    assert result.fell_back is True
    assert result.backend in ("annealing", "greedy")
