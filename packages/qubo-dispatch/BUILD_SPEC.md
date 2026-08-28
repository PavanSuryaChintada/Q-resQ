# BUILD SPEC — qubo-dispatch

Implementation contract for `packages/qubo-dispatch`. Every file, its exact responsibility, and the traps.

Build in the order listed. Each step has a test that must pass before the next.

> **Read `../../CLAUDE.md` first.** The rules there override anything here.

---

## Ground rules

- **Zero imports from `services/` or `apps/`.** This package is published standalone under MIT. If it imports application code, that's a bug.
- **Qiskit is an optional dependency.** `import qubo_dispatch` must succeed with Qiskit uninstalled. Import it lazily inside `solvers/qaoa.py`, never at module top level.
- **No solver returns an unvalidated result.** `validate_constraints` is the gate.
- **Type hints on every public function.** Pydantic-style dataclasses for the data model.

---

## Build order

```
1. types.py           — no test, just the shapes
2. formulation.py     — test_formulation.py
3. penalties.py       — test_penalties.py
4. solvers/greedy.py  — test_constraints.py (greedy only)   → RELEASE GATE begins
5. solvers/annealing.py
6. solvers/ortools_solver.py
7. router.py          — test_fallback.py                     → RELEASE GATE
8. partition.py       — test_partition.py
9. solvers/qaoa.py    — test_constraints.py (all backends)   → RELEASE GATE complete
10. benchmark.py
```

**Do QAOA last.** It's the highest-risk piece and the one most likely to eat hours on a dependency conflict. Everything else must already work without it.

---

## 1 · `types.py`

```python
@dataclass(frozen=True)
class Unit:
    id: str
    capacity: int
    position: tuple[float, float]     # (lat, lon)
    kind: str = "boat"

@dataclass(frozen=True)
class Request:
    id: str
    severity: float                   # 0..1, computed upstream
    people: int
    position: tuple[float, float]

@dataclass
class DispatchProblem:
    units: list[Unit]
    requests: list[Request]
    travel_time_s: dict[tuple[str, str], float]   # (unit_id, request_id) -> seconds
    alpha: float = 0.3                # travel-vs-severity tradeoff

@dataclass
class QUBO:
    Q: dict[tuple[int, int], float]   # upper-triangular sparse
    n_vars: int
    index: dict[tuple[str, str], int] # (unit_id, request_id) -> variable index
    reverse: dict[int, tuple[str, str]]
    offset: float = 0.0
    lam: float = 0.0                  # the tuned penalty, kept for reporting

@dataclass
class DispatchResult:
    assignments: list[tuple[str, str]]   # (unit_id, request_id)
    objective: float
    backend: str
    fell_back: bool
    solve_ms: int
    qubit_count: int | None = None
```

**Trap:** `travel_time_s` may be missing pairs (a unit that cannot reach a request at all because every road is flooded). Treat a missing key as unreachable and **do not create a variable for that pair**. This shrinks the QUBO for free and is the single easiest optimization in the package.

---

## 2 · `formulation.py`

```python
def build_qubo(problem: DispatchProblem, lam: float) -> QUBO
```

### Variable indexing

One binary variable per *reachable* (unit, request) pair. Build `index` and `reverse` together. `n_vars = len(index)`.

### Normalisation — do this before anything else

```python
max_value  = max(r.severity * r.people for r in problem.requests)
max_travel = max(problem.travel_time_s.values())
```

Then per pair:
```python
value_norm  = (req.severity * req.people) / max_value      # 0..1
travel_norm = travel_time_s[(u.id, r.id)] / max_travel     # 0..1
```

**Trap:** guard against `max_value == 0` and `max_travel == 0`. Divide-by-zero here produces NaNs that propagate silently into the Q matrix and the solver returns nonsense with no error.

### Linear terms — go on the diagonal

QUBO has no separate linear vector. Because binary variables satisfy `x² = x`, linear coefficients live at `Q[(i, i)]`.

```python
Q[(k, k)] += -value_norm + alpha * travel_norm
```

Negative because we're minimising and want to *reward* covering high-value requests.

### Constraint 1 — at most one unit per request

For each request, take every pair of units `i < i'` that can reach it:

```python
Q[(min(k1,k2), max(k1,k2))] += 2.0 * lam
```

### Constraint 2 — at most one request per unit

Same, transposed: for each unit, every pair of requests `j < j'` it can reach.

```python
Q[(min(k1,k2), max(k1,k2))] += 2.0 * lam
```

### The three traps in this function

1. **Do not use the exactly-one penalty.** `(Σx − 1)²` forces every request to receive exactly one unit. With 15 units and 200 requests that's infeasible and the solver returns garbage. We derive from `y(y−1) = 0` where `y = Σᵢ xᵢⱼ`. Expanding gives `y² − y`; since `x² = x` the diagonal terms cancel, leaving only the pairwise cross terms above. **There is no `−1` and no constant offset in our penalty.** If your expansion produced diagonal terms or an offset, it's wrong.

2. **Keep Q strictly upper-triangular.** Always store at `(min, max)`. Writing both `(i,j)` and `(j,i)` double-counts every quadratic term and silently doubles your effective penalty.

3. **The factor of 2 is correct.** `y² = Σᵢ xᵢ + 2·Σ_{i<i'} xᵢxᵢ'`. Dropping the 2 halves the penalty and lets the solver cheat on borderline instances — which will pass small tests and fail at demo scale.

### Objective evaluation

```python
def evaluate(qubo: QUBO, x: dict[int, int]) -> float
```
Straight `Σ Q[i][j]·x[i]·x[j] + offset`. Every solver reports through this so the benchmark compares like with like.

---

## 3 · `penalties.py`

```python
def tune_penalty(problem: DispatchProblem) -> float:
    bound = 1.0 + problem.alpha * 1.0    # both terms normalised to 0..1
    return 1.2 * bound
```

That's it — it's this simple *because* we normalise in `formulation.py`. Keep the function anyway: it documents the reasoning, and it's the answer to the question judges ask.

Write this comment in the source verbatim:

```python
# lambda must exceed the maximum objective gain from violating a
# constraint, or the optimizer breaks it for points. But oversized
# penalties flatten the energy landscape and stall COBYLA inside
# QAOA — every feasible solution starts to look identical. 1.2x is
# the smallest safe margin.
```

Expose `tune_penalty(problem, margin=1.2)` so the benchmark can sweep margin values if there's time. That sweep is a great backup slide.

---

## 4 · `solvers/base.py`

```python
class Solver(Protocol):
    name: str
    def solve(self, qubo: QUBO, problem: DispatchProblem,
              timeout_s: float) -> DispatchResult: ...
```

Plus the gate, which lives here because everything calls it:

```python
def validate_constraints(assignments: list[tuple[str, str]]) -> bool:
    units    = [u for u, _ in assignments]
    requests = [r for _, r in assignments]
    return len(units) == len(set(units)) and len(requests) == len(set(requests))
```

Three lines. It's the most important function in the package.

---

## 5 · `solvers/greedy.py`

Sort requests by `severity * people` descending. For each, assign the nearest unused unit that can reach it. Skip if none.

**Constraints:** stdlib only. No numpy, no scipy. This is the floor of the fallback chain and it must be incapable of failing.

Also export `greedy_bitstring(qubo, problem) -> dict[int, int]` — QAOA warm-starts from it.

---

## 6 · `solvers/annealing.py`

Standard simulated annealing on the QUBO. Pure Python.

- Start from the greedy solution, not random
- Geometric cooling: `T = T0 * (0.95 ** step)`, `T0 = lam`
- Single-bit flips, delta-evaluated (do **not** recompute the full objective each step — that's O(n²) per flip and it will be too slow)
- Respect `timeout_s` with a wall-clock check every 100 steps
- Return the best *feasible* solution seen, not the last one

**Trap:** annealing can wander into infeasible states mid-run. That's fine and expected — track the best feasible separately.

---

## 7 · `solvers/ortools_solver.py`

CP-SAT with the constraints declared natively rather than as penalties:

```python
for request: model.AddAtMostOne([x[u][r] for u in reachable_units])
for unit:    model.AddAtMostOne([x[u][r] for r in reachable_requests])
model.Maximize(sum(value_norm[u][r]*x[u][r] - alpha*travel_norm[u][r]*x[u][r] ...))
```

**Important:** report the objective through `formulation.evaluate()` on the resulting assignment, not CP-SAT's internal objective. The two use different sign conventions and comparing them directly makes the benchmark meaningless.

This is the honest production baseline. Expect it to win.

---

## 8 · `router.py`

```python
FALLBACK_CHAINS = {
    "qaoa":      ["qaoa", "annealing", "greedy"],
    "annealing": ["annealing", "greedy"],
    "ortools":   ["ortools", "greedy"],
    "greedy":    ["greedy"],
}

def solve(problem, backend="qaoa", timeout_s=10.0) -> DispatchResult
```

For each solver in the chain: try it, catch **every** exception including `ImportError`, run `validate_constraints`, return on success with `fell_back` set correctly. Log each fall-through at WARNING with the solver name and the reason.

If greedy itself fails, raise. That's a genuine bug, not a fallback case.

**Trap:** catching only `Exception` misses `KeyboardInterrupt` and some Qiskit C-level errors. Catch `BaseException` for the solver call specifically, re-raising `KeyboardInterrupt`.

---

## 9 · `partition.py`

```python
def partition(problem, max_requests_per_zone=5,
              max_units_per_zone=4) -> list[DispatchProblem]
```

1. `k = ceil(len(requests) / max_requests_per_zone)`
2. KMeans on request lat/lon (`sklearn.cluster.KMeans`, `n_init=10`)
3. **Enforce the cap** — KMeans does not respect size limits. Post-process: for any oversized cluster, move its farthest-from-centroid members to the nearest cluster with room.
4. Assign units to zones by distance to zone centroid, capped at `max_units_per_zone`, greedily in order of zone severity total
5. Slice `travel_time_s` down to each zone's pairs

```python
def solve_partitioned(problem, backend="qaoa", max_workers=None) -> DispatchResult
```
`ProcessPoolExecutor`, one zone per worker, merge assignments, sum objectives.

**Traps:**
- Zones with zero units must be skipped, not solved. An empty problem crashes some solvers.
- `ProcessPoolExecutor` pickles arguments — `DispatchProblem` must be picklable. Frozen dataclasses are; lambdas and open connections are not.
- Run `validate_constraints` on the *merged* result too. Per-zone validity does not guarantee global validity if the unit assignment step has a bug.

---

## 10 · `solvers/qaoa.py`

**Lazy import. This is the whole point of the package's fallback design:**

```python
def solve(self, qubo, problem, timeout_s):
    try:
        from qiskit_aer.primitives import Sampler
        from qiskit.circuit.library import QAOAAnsatz
        from qiskit.quantum_info import SparsePauliOp
    except ImportError as e:
        raise SolverUnavailable("qiskit not installed") from e
```

### QUBO → Ising

Substitute `x = (1 - z) / 2` and build a `SparsePauliOp`. Constant terms fold into the offset and can be dropped — they shift every energy equally.

**Trap:** get the sign convention right. Test it: on a 4-variable problem, brute-force all 16 assignments, and confirm the Ising energy ordering matches the QUBO objective ordering exactly. If it doesn't, everything downstream is silently inverted and QAOA will confidently return the *worst* plan.

### Config

```python
p = 3
optimizer = COBYLA(maxiter=100)
shots = 1024
```

- **Warm start:** initial parameters derived from the greedy bitstring, not random. Improves convergence and it's the honest answer to "how did you make it work at this size."
- Take the **best measured bitstring**, not the mean or the most frequent.
- Hard guard: raise if `n_vars > 24`. Aer statevector is 268 MB at 24 qubits and 17 GB at 30 — it will kill the process, and a crash mid-demo is much worse than a fallback.
- Expose `aer_method="statevector" | "matrix_product_state"`. MPS is the headroom answer when a judge asks about larger zones.
- Respect `timeout_s` — COBYLA doesn't take a wall-clock limit, so check elapsed time in the cost-function callback and raise to trigger the fallback.

---

## 11 · `benchmark.py`

```python
def benchmark(problem, backends=("qaoa","annealing","ortools","greedy")) -> list[dict]
```

Same problem, same tuned `lam`, each backend. Return `backend, objective, solve_ms, constraints_valid, qubit_count`.

**Do not sort so quantum appears first. Do not filter losing rows.** A table where QAOA wins every row reads as fabricated. Honest parity reads as engineering, and it pre-empts the hostile question.

---

## Tests

### `test_constraints.py` — RELEASE GATE
500 random instances (2–5 units, 3–8 requests, random severities and travel times). For every backend available, assert `validate_constraints` passes. Skip QAOA if Qiskit is absent — do not fail.

### `test_fallback.py` — RELEASE GATE
Monkeypatch the Qiskit import to raise. Assert `solve(problem, backend="qaoa")` still returns a valid assignment with `fell_back == True` and `backend in ("annealing", "greedy")`.

### `test_formulation.py`
On instances small enough to brute-force (≤ 12 variables), enumerate every assignment. Assert the QUBO minimum is feasible, and that it matches the brute-force optimum of the objective. **This is the test that catches a wrong penalty expansion** — write it early.

### `test_penalties.py`
Assert no infeasible assignment ever scores below the best feasible one, across random instances.

### `test_partition.py`
Every request lands in exactly one zone. No zone exceeds the caps. Merged assignments pass global validation.

---

## `pyproject.toml`

```toml
[project]
name = "qubo-dispatch"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["numpy>=1.26", "scikit-learn>=1.5"]

[project.optional-dependencies]
quantum = ["qiskit==1.2.4", "qiskit-aer==0.15.1", "qiskit-optimization==0.6.1"]
classical = ["ortools==9.11.4210"]

[project.license]
text = "MIT"
```

**Pin the Qiskit versions exactly and commit the lockfile in hour 1.** The 1.0 API change is real and version drift here is the single most likely thing to eat your night.
