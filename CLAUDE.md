# CLAUDE.md — Build Rules for PRAHARI

> Read this file completely before writing any code. It overrides your defaults.
> Full specs live in `docs/`. This file is the contract.

---

## 1. What this is

**PRAHARI** — a disaster prediction and rescue-dispatch platform, built in 24 hours for HackSprint 2.0 (AITAM, Tekkali).

The system does **two separate things**. Never conflate them:

| | Problem | Method | Module |
|---|---|---|---|
| **A** | *Which areas will flood?* | Supervised ML on terrain + rainfall | `services/risk/` |
| **B** | *Given 15 boats and 200 rescue calls, who goes where?* | Constrained combinatorial optimization (QUBO) | `services/dispatch/` |

Problem A is prediction. Problem B is decision-making. ML cannot do B — there is no labelled dataset of "optimal rescue decisions", and neural networks cannot enforce hard constraints. B is where the quantum work lives.

**Demo scenario:** Cyclone Titli, Srikakulam district, Andhra Pradesh, 11 October 2018.

---

## 2. Non-negotiable rules

### 2.1 Never claim quantum advantage
QAOA on a 20-qubit simulator does **not** beat OR-Tools. Anywhere the UI, README, or code comments mention quantum, the framing is:

> "Quantum-ready hybrid dispatch. Benchmarked against classical solvers. Parity at current scale, hardware-ready formulation."

If you generate copy claiming quantum is faster or better, you have introduced a bug. The benchmark table must show honest results **including losses**.

### 2.2 Quantum is never in the critical path
The dispatch service must produce a valid assignment even if Qiskit is uninstalled, crashes, or times out. Solver selection is a runtime parameter with a hard fallback chain:

```
qaoa → (timeout 10s or exception) → simulated_annealing → (fail) → greedy
```

`greedy` has no dependencies beyond stdlib and must never fail.

### 2.3 Deploy from hour zero
Before building features, get an empty FastAPI service on Railway and an empty Vite app on Vercel, both green. Teams die deploying at hour 20.

### 2.4 Scope discipline
Four features fully working beats nine features half-built:
1. Risk map
2. Prioritised dispatch (with solver benchmark)
3. Offline request capture
4. Operations dashboard

Anything else is cut. Do not add features not listed in `docs/PRD.md`.

### 2.5 No AI-slop visual design
Read `docs/DESIGN.md` before writing any CSS or component. Hard bans:
- No gradients of any kind (no `linear-gradient`, no `bg-gradient-to-*`)
- No glassmorphism, backdrop-blur, or translucent frosted cards
- No purple/violet/indigo anywhere
- No glow effects, no coloured box-shadows
- No emoji in the UI
- No border-radius above `2px`
- No shadcn default theme, no Material, no Bootstrap

Colour carries **severity meaning only**. If a colour is not encoding data, it is greyscale.

---

## 3. Stack — pinned

**Frontend**
- Vite + React 18 + TypeScript
- Tailwind CSS (config locked to the tokens in `docs/DESIGN.md` — no arbitrary values)
- MapLibre GL JS (not Leaflet, not Mapbox GL — licensing)
- `idb` for IndexedDB
- Workbox for the service worker
- TanStack Query for server state

**Backend**
- FastAPI + Uvicorn, Python 3.11
- Pydantic v2 for all request/response models
- `supabase-py` for DB access

**Data**
- Supabase (Postgres 15 + PostGIS + Realtime + Auth)

**Risk model**
- LightGBM, scikit-learn
- `rasterio`, `pysheds` (HAND computation), `osmnx`, `networkx`

**Optimization**
- `qiskit==1.2.4`, `qiskit-aer==0.15.1`, `qiskit-optimization==0.6.1` — **pin exactly, commit the lockfile in hour 1**
- `ortools` for the classical baseline
- Pure-Python simulated annealing (no extra dependency)

**Do not add libraries not listed here without a stated reason.**

---

## 4. Repository layout

```
prahari/
├── CLAUDE.md
├── README.md
├── docs/
│   ├── PRD.md
│   ├── TRD.md
│   ├── WORKFLOW.md
│   └── DESIGN.md
├── packages/
│   └── qubo-dispatch/          # standalone, open-source, MIT
│       ├── README.md
│       ├── BUILD_SPEC.md       # file-by-file implementation contract
│       ├── pyproject.toml
│       ├── src/qubo_dispatch/
│       │   ├── formulation.py  # build QUBO from a DispatchProblem
│       │   ├── penalties.py    # auto-tune lambda from objective bound
│       │   ├── partition.py    # constrained k-means zoning
│       │   ├── solvers/
│       │   │   ├── base.py     # Solver protocol
│       │   │   ├── qaoa.py
│       │   │   ├── annealing.py
│       │   │   ├── ortools_solver.py
│       │   │   └── greedy.py
│       │   └── router.py       # solve(problem, backend=...) + fallback chain
│       └── tests/
│           ├── test_constraints.py   # MUST pass: no double-assignment
│           └── test_fallback.py
├── services/
│   └── api/
│       ├── schema.sql          # runnable — source of truth for the DB
│       ├── BUILD_SPEC.md       # file-by-file implementation contract
│       ├── main.py
│       ├── routers/            # risk, requests, dispatch, units, benchmark
│       ├── risk/                # feature engineering, LightGBM, HAND
│       ├── roads/               # OSM graph, flood-aware edge weights
│       └── seed/                # Titli scenario generator
└── apps/
    └── web/
        ├── src/
        │   ├── components/
        │   ├── routes/          # /map  /dispatch  /requests  /benchmark
        │   ├── lib/             # offline queue, sync, api client
        │   └── styles/tokens.css
        └── public/tiles/         # PMTiles for Srikakulam, z10–14
```

`packages/qubo-dispatch` must have **zero imports** from `services/` or `apps/`. It is publishable on its own.

---

## 5. The QUBO — implement exactly this

Variable: `x[i][j] = 1` if unit *i* is dispatched to request *j*.

**Objective**
```
H_cost = -Σ_ij (severity_j · urgency_j · people_j) · x_ij
         +Σ_ij (α · travel_time_ij) · x_ij
```
Normalise both terms to [0,1] before combining. `α` default 0.3.

**Constraint 1 — each request served at most once**

Do **not** use the textbook `(Σ_i x_ij − 1)²` penalty. In a real disaster there are more requests than units, so "exactly one" is infeasible and the solver returns garbage. Use at-most-one:

```
H_request = λ₁ · Σ_j Σ_{i<i'} 2 · x_ij · x_i'j
```

Pairwise conflict terms only. No slack variables, no extra qubits.

**Constraint 2 — each unit dispatched at most once**
```
H_unit = λ₂ · Σ_i Σ_{j<j'} 2 · x_ij · x_ij'
```

**Penalty tuning** (`penalties.py`, compute at runtime, never hardcode):
```
bound = max_ij |severity_j · urgency_j · people_j| + α · max(travel_time)
λ = 1.2 · bound
```
Comment in the code why 1.2 and not 10: oversized penalties flatten the energy landscape and stall the QAOA optimizer.

**QAOA config**
- Zone cap: ≤ 24 binary variables (Aer statevector: 24 qubits ≈ 268 MB; 30 qubits ≈ 17 GB and dies)
- Target zone size: 4 units × 5 requests = 20 qubits
- Depth `p = 3`
- Optimizer: COBYLA
- Shots: 1024, take the **best measured bitstring**, not the mean
- **Warm start**: initialise parameters from the greedy solution, not random

**Scaling is horizontal.** Never grow the QUBO. Partition geographically into zones of ≤ 5 requests, solve in parallel, merge. Qubit count per solve stays constant whether there are 40 requests or 4,000.

---

## 6. Testing floor

Two tests must pass before anything is demoed:

- `test_constraints.py` — across 500 random problem instances, no returned assignment ever double-books a unit or a request. Any solver, any backend.
- `test_fallback.py` — with Qiskit monkeypatched to raise on import, `solve()` still returns a valid assignment.

---

## 7. Copy rules

- Sentence case everywhere. Not Title Case.
- Active voice. A button that says "Dispatch" produces a log line that says "Dispatched."
- Name things as an emergency officer would: "rescue units", "requests", "zones" — never "entities", "objects", "records".
- Errors state what happened and what to do. No apologies.
- Empty states are instructions, not decoration.
- Never write "leverage", "seamless", "powerful", "revolutionize", "cutting-edge", "harness".

---

## 7b. Where the implementation contracts live

Before writing code in either package, read its build spec:

- `packages/qubo-dispatch/BUILD_SPEC.md` — every file, its exact
  responsibility, the build order, and the traps. Includes the three
  ways the QUBO expansion is commonly got wrong.
- `services/api/BUILD_SPEC.md` — same, for the FastAPI service.
- `services/api/schema.sql` — runnable. Apply it with psql; never
  retype the DDL from `docs/TRD.md`.

## 8. When you are unsure

Ask rather than assume. If a spec in `docs/` conflicts with this file, this file wins. If you are about to add a dependency, invent a colour, add a feature, or claim a performance result — stop and ask first.
