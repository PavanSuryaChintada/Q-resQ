import itertools

import pytest

qiskit = pytest.importorskip("qiskit")

from qubo_dispatch.formulation import build_qubo, evaluate
from qubo_dispatch.solvers.base import validate_constraints
from qubo_dispatch.solvers.qaoa import QaoaSolver, SolverUnavailable, qubo_to_ising
from qubo_dispatch.types import DispatchProblem, Request, Unit


def _four_variable_problem():
    # 2 units x 2 requests, fully connected = 4 variables, brute-forceable
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


def test_ising_energy_ordering_matches_qubo_objective_ordering_exactly():
    from qiskit.quantum_info import Statevector

    problem = _four_variable_problem()
    qubo = build_qubo(problem, lam=1.5)
    hamiltonian, offset = qubo_to_ising(qubo)
    n = qubo.n_vars

    for bits in itertools.product([0, 1], repeat=n):
        x = dict(enumerate(bits))
        qubo_energy = evaluate(qubo, x)

        # computational basis label: leftmost char = qubit n-1, matching
        # the position convention used when building the Hamiltonian
        label = "".join(str(x[n - 1 - i]) for i in range(n))
        state = Statevector.from_label(label)
        ising_energy = state.expectation_value(hamiltonian).real + offset

        assert ising_energy == pytest.approx(qubo_energy, abs=1e-9), (
            f"mismatch at x={x}: qubo={qubo_energy}, ising={ising_energy}"
        )


def test_solve_returns_a_valid_feasible_assignment():
    problem = _four_variable_problem()
    qubo = build_qubo(problem, lam=1.5)

    result = QaoaSolver().solve(qubo, problem, timeout_s=30.0)

    assert result.backend == "qaoa"
    assert result.fell_back is False
    assert validate_constraints(result.assignments) is True
    assert result.qubit_count == qubo.n_vars


def test_raises_solver_unavailable_above_the_24_qubit_guard():
    units = [Unit(id=f"u{i}", capacity=1, position=(0.0, 0.0)) for i in range(5)]
    requests = [Request(id=f"r{j}", severity=0.5, people=1, position=(0.0, 0.0)) for j in range(5)]
    travel_time_s = {(u.id, r.id): 100.0 for u in units for r in requests}  # 25 variables
    problem = DispatchProblem(units=units, requests=requests, travel_time_s=travel_time_s)
    qubo = build_qubo(problem, lam=1.5)
    assert qubo.n_vars == 25

    with pytest.raises(SolverUnavailable):
        QaoaSolver().solve(qubo, problem, timeout_s=30.0)
