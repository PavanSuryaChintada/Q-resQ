# qubo-dispatch

Formulate emergency rescue dispatch as a QUBO. Solve it with quantum or classical backends behind one interface.

MIT licensed. No dependency on any application code.

---

## The problem

You have *m* rescue units and *n* requests. Each request has a severity and a people count. Travel time between any unit and any request is known and changes as roads flood. Assign units to requests to maximise lives-weighted coverage while minimising travel.

Each unit takes one request per round; each request is served by at most one unit. Re-solve as units free up — a rolling horizon.

This is a capacitated assignment problem. NP-hard, and a natural fit for QUBO.

---

## Install

```bash
pip install qubo-dispatch          # classical solvers only
pip install qubo-dispatch[quantum] # adds qiskit + aer
```

Quantum is optional. Without it, the library still solves everything.

---

## Use

```python
from qubo_dispatch import DispatchProblem, Unit, Request, solve

problem = DispatchProblem(
    units=[Unit(id="boat-03", capacity=6, position=(18.30, 83.89))],
    requests=[Request(id="req-0187", severity=0.82, people=4,
                      position=(18.34, 83.91))],
    travel_time_s={("boat-03", "req-0187"): 940},
)

result = solve(problem, backend="qaoa", timeout_s=10.0)

result.assignments   # [("boat-03", "req-0187")]
result.backend       # "qaoa" — or the solver it fell back to
result.fell_back     # True if the requested backend failed
result.objective
result.solve_ms
```

`solve()` never returns an invalid assignment and never raises for solver failure. It falls through the chain to `greedy`, which has no dependencies beyond the standard library.

---

## Formulation

`x[i][j] = 1` if unit *i* is dispatched to request *j*.

**Objective**
```
H_cost = -Σ_ij (severity_j · people_j) · x_ij  +  α · Σ_ij travel_norm_ij · x_ij
```
Both terms normalised to [0,1]. `α` defaults to 0.3.

**Constraints — at most one, not exactly one**

The textbook penalty for "one unit per request" is `(Σ_i x_ij − 1)²`, which forces *exactly* one. In a disaster there are more requests than units, so exactly-one is infeasible and the solver returns garbage.

Use `y(y−1) = 0`, where `y = Σ_i x_ij`. Since `x² = x` for binary variables, the diagonal terms cancel:

```
H_request = λ₁ · Σ_j Σ_{i<i'} 2 · x_ij · x_i'j
H_unit    = λ₂ · Σ_i Σ_{j<j'} 2 · x_ij · x_ij'
```

Pairwise conflict terms only. **No slack variables, no additional qubits.**

**Penalty tuning** — computed at runtime, never hardcoded:

```
bound = max_j(severity_j · people_j) + α · max_ij(travel_norm_ij)
λ = 1.2 · bound
```

The penalty must exceed the maximum objective gain from violating the constraint, or the optimizer will break it for points. But oversized penalties flatten the energy landscape and stall QAOA's classical optimizer, because every feasible solution starts to look the same. 1.2 is the smallest safe margin.

---

## Scaling

The QUBO never grows.

```python
from qubo_dispatch import partition, solve_partitioned

result = solve_partitioned(problem, max_requests_per_zone=5,
                           max_units_per_zone=4, backend="qaoa")
```

Requests are partitioned geographically by constrained k-means, each zone becomes an independent QUBO, and zones solve in parallel. **Qubit count per solve stays constant regardless of total problem size.** Scaling is horizontal.

Known limitation: a unit near a zone boundary may be better used in the neighbouring zone. Boundary suboptimality is traded for constant-size subproblems, and re-partitioning each round prevents the error accumulating.

---

## Backends

| Backend | Requires | Notes |
|---|---|---|
| `qaoa` | qiskit, qiskit-aer | `p=3`, COBYLA, 1024 shots, warm-started from greedy. Returns the best measured bitstring, not the mean. |
| `annealing` | — | Simulated annealing, geometric cooling. Pure Python. |
| `ortools` | ortools | CP-SAT. The honest production baseline. |
| `greedy` | — | Severity-descending, nearest available unit. Cannot fail. |

**Qubit budget.** Aer statevector: 24 qubits ≈ 268 MB, 30 qubits ≈ 17 GB. Cap zones at 24 variables; 20 is comfortable. For more headroom, set `aer_method="matrix_product_state"`, which handles more qubits while entanglement stays low.

---

## Benchmarks

```python
from qubo_dispatch import benchmark
benchmark(problem, backends=["qaoa", "annealing", "ortools", "greedy"])
```

Returns objective, wall-clock time, constraint validity, and qubit count per backend.

**On results:** at these problem sizes QAOA does not beat OR-Tools. It reaches parity on small zones and loses on larger ones. This library exists because the formulation work — getting a real dispatch problem into a valid QUBO with correctly tuned penalties — has to happen before hardware is ready, not after. The solver is a runtime parameter.

Do not use this library to claim a quantum speedup. It will not support the claim.

---

## Tests

```bash
pytest
```

- `test_constraints.py` — 500 random instances, no double-booking, any backend
- `test_fallback.py` — Qiskit patched to fail on import, valid assignment still returned
- `test_penalties.py` — λ ≥ bound holds across random instances
- `test_partition.py` — every request lands in exactly one zone, sizes within cap

---

## License

MIT.
