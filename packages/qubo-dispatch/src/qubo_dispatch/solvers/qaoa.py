"""QAOA on Aer, warm-started from greedy. See BUILD_SPEC.md §10.

Lazy import throughout - this is the whole point of the package's
fallback design. `import qubo_dispatch` must succeed with Qiskit
uninstalled.
"""

from __future__ import annotations

import math
import time

from qubo_dispatch.formulation import evaluate
from qubo_dispatch.solvers.greedy import greedy_bitstring
from qubo_dispatch.types import DispatchProblem, DispatchResult, QUBO

MAX_QUBITS = 24  # Aer statevector: 24 qubits ~268MB, 30 qubits ~17GB and dies


class SolverUnavailable(Exception):
    pass


class _TimeoutExceeded(Exception):
    pass


def qubo_to_ising(qubo: QUBO):
    """x = (1-z)/2 substitution. Returns (SparsePauliOp, offset).

    Bit-position convention: variable k maps to qubit k, placed at
    string index (n-1-k) - i.e. Qiskit's usual little-endian layout
    where the rightmost character is qubit 0. Verified against a
    brute-force Statevector expectation check in
    test_solvers_qaoa.py::test_ising_energy_ordering_matches_qubo_objective_ordering_exactly.
    """
    from qiskit.quantum_info import SparsePauliOp

    n = qubo.n_vars
    offset = qubo.offset
    terms: dict[str, float] = {}
    identity = "I" * n

    def add(pauli: str, coeff: float) -> None:
        terms[pauli] = terms.get(pauli, 0.0) + coeff

    for (i, j), coeff in qubo.Q.items():
        if i == j:
            offset += coeff / 2.0
            z = list(identity)
            z[n - 1 - i] = "Z"
            add("".join(z), -coeff / 2.0)
        else:
            offset += coeff / 4.0
            zi = list(identity)
            zi[n - 1 - i] = "Z"
            add("".join(zi), -coeff / 4.0)
            zj = list(identity)
            zj[n - 1 - j] = "Z"
            add("".join(zj), -coeff / 4.0)
            zij = list(identity)
            zij[n - 1 - i] = "Z"
            zij[n - 1 - j] = "Z"
            add("".join(zij), coeff / 4.0)

    pauli_list = [(p, c) for p, c in terms.items() if abs(c) > 1e-12]
    if not pauli_list:
        pauli_list = [(identity, 0.0)]
    return SparsePauliOp.from_list(pauli_list), offset


def _bitstring_to_x(bitstring: str, n: int) -> dict[int, int]:
    # Aer/Qiskit counts keys are little-endian: rightmost char = qubit 0
    return {k: int(bitstring[n - 1 - k]) for k in range(n)}


class QaoaSolver:
    name = "qaoa"

    def solve(self, qubo: QUBO, problem: DispatchProblem, timeout_s: float,
              p: int = 3, shots: int = 1024, maxiter: int = 100,
              aer_method: str = "statevector") -> DispatchResult:
        start = time.monotonic()
        try:
            import numpy as np
            from qiskit import transpile
            from qiskit.circuit.library import QAOAAnsatz
            from qiskit_aer import AerSimulator
            from scipy.optimize import minimize
        except ImportError as exc:
            raise SolverUnavailable("qiskit/qiskit-aer not installed") from exc

        if qubo.n_vars > MAX_QUBITS:
            raise SolverUnavailable(
                f"qubo has {qubo.n_vars} variables, exceeds the {MAX_QUBITS}-qubit "
                f"statevector guard - partition into smaller zones"
            )

        if qubo.n_vars == 0:
            return DispatchResult(assignments=[], objective=qubo.offset, backend=self.name,
                                   fell_back=False, solve_ms=0, qubit_count=0)

        hamiltonian, offset = qubo_to_ising(qubo)
        n = qubo.n_vars

        ansatz = QAOAAnsatz(cost_operator=hamiltonian, reps=p)
        ansatz.measure_all()
        backend = AerSimulator(method=aer_method)
        # QAOAAnsatz is a blueprint circuit (opaque "QAOA" instruction)
        # until decomposed - Aer can only run basis gates
        transpiled = transpile(ansatz, backend)

        # warm start: derive initial angles from the greedy bitstring's
        # own Ising energy rather than random values - a small, fixed
        # mixer angle plus a cost angle scaled by how far greedy's
        # energy sits from the constraint bound, so a good greedy
        # solution starts the search near a shallow part of the cost
        # landscape instead of at a random point on it.
        greedy_x = greedy_bitstring(qubo, problem)
        greedy_energy = evaluate(qubo, greedy_x)
        scale = 1.0 / (1.0 + abs(greedy_energy))
        initial_point = []
        for _ in range(p):
            initial_point.append(scale * math.pi / 4.0)  # gamma
        for _ in range(p):
            initial_point.append(math.pi / 8.0)  # beta
        initial_point = np.array(initial_point)

        def expected_energy(params: "np.ndarray") -> float:
            if time.monotonic() - start > timeout_s:
                raise _TimeoutExceeded()
            bound = transpiled.assign_parameters(params)
            result = backend.run(bound, shots=256).result()
            counts = result.get_counts()
            total_shots = sum(counts.values())
            energy = 0.0
            for bitstring, count in counts.items():
                x = _bitstring_to_x(bitstring.replace(" ", ""), n)
                energy += evaluate(qubo, x) * (count / total_shots)
            return energy

        try:
            opt = minimize(expected_energy, initial_point, method="COBYLA",
                            options={"maxiter": maxiter})
            best_params = opt.x
        except _TimeoutExceeded:
            best_params = initial_point

        bound = transpiled.assign_parameters(best_params)
        final = backend.run(bound, shots=shots).result()
        counts = final.get_counts()

        best_x = greedy_x
        best_energy = greedy_energy
        for bitstring, _count in counts.items():
            x = _bitstring_to_x(bitstring.replace(" ", ""), n)
            energy = evaluate(qubo, x)
            if energy < best_energy:
                best_energy = energy
                best_x = x

        assignments = [qubo.reverse[k] for k, v in best_x.items() if v == 1]
        solve_ms = int((time.monotonic() - start) * 1000)
        return DispatchResult(
            assignments=assignments,
            objective=best_energy,
            backend=self.name,
            fell_back=False,
            solve_ms=solve_ms,
            qubit_count=n,
        )
