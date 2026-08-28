# PRAHARI

**Disaster prediction and rescue dispatch for Srikakulam district.**

HackSprint 2.0 · AITAM Tekkali · Problem Statement #1

---

## The idea in two sentences

Every disaster-management project stops at prediction: rainfall goes in, a risk map comes out, the demo ends. But a risk map does not rescue anyone — the moment a flood starts, an emergency officer has 15 boats, 200 rescue calls, and roads going underwater, and has to decide who gets reached first.

PRAHARI does both, and treats them as the two different problems they are.

| | Question | Method |
|---|---|---|
| **Prediction** | Which areas will flood? | LightGBM on terrain + rainfall |
| **Decision** | Who gets rescued first? | Constrained combinatorial optimization (QUBO) |

---

## Why a neural network cannot do the second one

**No training data.** There is no dataset of optimal rescue dispatch decisions. Nobody recorded the right answer — only what overwhelmed officials actually did.

**No hard constraints.** A neural network outputs probabilities. It can assign one boat to two places at once, because nothing in its architecture forbids it. An optimizer cannot return an invalid plan. In a rescue, an invalid plan is worse than none.

**No pattern to match.** Every disaster is a new configuration of units, requests, and impassable roads. This is search through a solution space, not recognition of a learned one.

Dispatch is combinatorial optimization. That is the problem class quantum optimization actually targets.

---

## Where quantum sits

Only in dispatch. Never in prediction, and never in the critical path.

The engine partitions open requests into geographic zones of ≤ 5, formulates each zone as a QUBO, and solves them in parallel through a solver chain:

```
qaoa → (timeout / failure) → simulated annealing → greedy
```

**Scaling is horizontal.** The QUBO never grows. 40 requests or 4,000, each solve is still ~20 qubits — you add zones, not qubits. This is the standard hybrid-decomposition pattern used in quantum optimization today.

### What we do not claim

QAOA on a 20-qubit simulator does not beat OR-Tools. The benchmark table in the app shows that, including the cases where quantum loses.

What we built is the **formulation** — turning "rescue dispatch over a flooding road network" into valid QUBO math with correctly tuned penalties. That is the part that does not change when the hardware does. The solver behind it is a runtime parameter.

**Near-term real use:** QPU access is queued and pay-per-shot, so quantum cannot sit inside a real-time rescue loop. But cyclones are forecast 48 hours ahead, and pre-positioning rescue assets during the warning window is an optimization that can afford to run slowly. That is a genuine use case that required no overstatement.

---

## Demo

**Cyclone Titli · Srikakulam · 11 October 2018.** Real IMD track data, real NASA POWER rainfall, real village and facility coordinates from OSM, real Copernicus terrain.

1. Rainfall accumulates, the risk map lights up
2. Rescue requests arrive and are triaged
3. Zones partition, dispatch solves in parallel
4. Offline request queued, syncs on reconnect
5. **A road floods. The engine re-solves. Assignments change.**

Step 5 is the point: the cost matrix changes as the water moves, which is why the dispatch engine has to exist at all.

---

## Stack

Vite · React · TypeScript · Tailwind · MapLibre GL · PMTiles · Workbox
FastAPI · Python 3.11 · Supabase (Postgres + PostGIS + Realtime)
LightGBM · rasterio · pysheds · osmnx · networkx
Qiskit + Aer · OR-Tools

---

## Repository

```
packages/qubo-dispatch/   standalone optimization library — MIT, zero repo coupling
services/api/             FastAPI: risk model, road graph, dispatch orchestration
apps/web/                 React operations console, offline-capable
docs/                     PRD · TRD · WORKFLOW · DESIGN
CLAUDE.md                 build rules — read this first
```

`packages/qubo-dispatch` imports nothing from the rest of the repo. It is published separately so anyone can use the formulation for their own dispatch problem.

---

## Running it

```bash
# Database
supabase start && psql $DATABASE_URL -f services/api/schema.sql

# API
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # versions are pinned — do not upgrade
uvicorn main:app --reload

# Seed the demo
curl -X POST localhost:8000/seed/titli

# Web
cd apps/web && npm install && npm run dev
```

The system runs with Qiskit uninstalled. It falls back to classical solvers and logs the fallback.

---

## Tests

```bash
cd packages/qubo-dispatch && pytest
```

Two are release gates:
- `test_constraints.py` — 500 random instances, no assignment ever double-books a unit or a request, on any backend
- `test_fallback.py` — with Qiskit patched to fail on import, a valid assignment still comes back
