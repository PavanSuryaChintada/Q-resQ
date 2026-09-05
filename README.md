# Q-resQ

**Disaster prediction and rescue dispatch for Srikakulam district.**

HackSprint 2.0 · AITAM Tekkali · Problem Statement #1

---

## The idea in two sentences

Every disaster-management project stops at prediction: rainfall goes in, a risk map comes out, the demo ends. But a risk map does not rescue anyone — the moment a flood starts, an emergency officer has 15 boats, 200 rescue calls, and roads going underwater, and has to decide who gets reached first.

Q-resQ does both, and treats them as the two different problems they are.

| | Question | Method |
|---|---|---|
| **Prediction** | Which areas will flood? | A weighted physical risk model on real terrain + rainfall (LightGBM trained alongside it) |
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

QAOA on a 20-qubit simulator does not beat OR-Tools. The benchmark panel in the app runs greedy, simulated annealing, OR-Tools, and QAOA on the identical problem and shows every result — objective, solve time, qubit count — including the runs where quantum loses. Nothing is hidden or reordered to make it look better.

What we built is the **formulation** — turning "rescue dispatch over a road network" into valid QUBO math with correctly tuned, auto-scaled penalties. That is the part that does not change when the hardware does. The solver behind it is a runtime parameter, with a fallback chain that never depends on Qiskit being installed, working, or fast.

---

## What's actually built

The app has an in-app **Solution Summary** tab that scores every requirement from the original problem statement — done / partial / not built, with the honest gap disclosed for anything short of "done." That tab is the current source of truth; this table is a snapshot of it:

| Requirement | Status | Notes |
|---|---|---|
| Risk prediction / early-warning | **Done** | Real Copernicus DEM (OpenTopography) + real rainfall, percentile-normalised 5-band heuristic. Historical replay uses real IMD RF25 data for 11 Oct 2018; a live check panel pulls real current rainfall from Open-Meteo for any nearby date. |
| Interactive risk map | **Done** | MapLibre GL, severity-coloured cells, click-to-inspect detail panel. |
| Multiple disaster types | **Done** | A header selector (cyclone / flood / urban flooding / landslide) re-weights the *same* real terrain and rainfall toward whichever physical driver matters most per hazard — not a new region, disclosed as such. |
| Nearby shelters / hospitals | **Not built** | Depends on OpenStreetMap's Overpass API — every public mirror tried (default host + two fallbacks) was unreachable from the build network. |
| Real-time notifications | **Partial** | An append-only dispatch ledger updates every 2–4s via polling, not a push channel. |
| Admin / rescue-team dashboard | **Done** | Layers, live risk check, cell detail, units, request queue (search + carousel), dispatch controls with benchmark, ledger — all collapsible panels. |
| Severity-based prioritisation | **Done** | Per-request severity (people, category, area risk, wait time) feeds the QUBO objective directly. |
| Offline / low-connectivity | **Not built** | Cut from scope to protect the risk + dispatch pipeline given the build window. |
| Vehicle-appropriate routing | **Done** | Ambulances/trucks/rescue teams route over real roads via OSRM's public routing API; boats stay on a direct line, which is the physically correct behaviour, not a shortfall. |
| Manual override | **Done** | Any open request can be assigned directly to any available unit from the request panel, bypassing the solver entirely, logged distinctly in the ledger. |

---

## Demo

**Cyclone Titli · Srikakulam · 11 October 2018.** Real Copernicus terrain, real IMD RF25 rainfall for the event.

1. Risk map renders from real terrain + rainfall; click any cell to see its score breakdown
2. Switch the disaster-type selector — same real data, re-weighted per hazard
3. Run the live risk check for today's date — a real call to Open-Meteo, not a replay
4. Seed the scenario, requests get triaged by severity automatically
5. Dispatch: pick a solver, including `qaoa` — it runs for real, on a real Aer simulator
6. Run the benchmark — every solver, same problem, no result hidden
7. Watch routes draw: roads for wheeled units, straight lines for boats
8. Everything lands in the append-only ledger on the right

---

## Stack

**Frontend** — Vite · React 19 · TypeScript · Tailwind · MapLibre GL · TanStack Query
**Backend** — FastAPI · Python 3.11
**Risk model** — real Copernicus DEM via OpenTopography, real IMD RF25 rainfall, `rasterio` + `pysheds` (HAND/TWI/slope), LightGBM trained on real flood labels
**Live data** — Open-Meteo (current/forecast rainfall), OSRM public API (road-following routes)
**Optimization** — `qiskit` + `qiskit-aer` + `qiskit-optimization`, OR-Tools, pure-Python simulated annealing
**Database** — Supabase is provisioned (schema applied, credentials configured) but the running app currently reads/writes in-memory stores, not the database — disclosed rather than left implicit
**Not wired** — `osmnx`/`networkx` self-hosted road graph and OSM facility data were attempted; every Overpass API mirror tried was unreachable from the build network, so OSRM's public API stands in for road routing instead, and the facilities layer isn't built

---

## Repository

```
packages/qubo-dispatch/   standalone optimization library — MIT, zero repo coupling
services/api/             FastAPI: risk model, dispatch orchestration, road routing
  risk/                     terrain features, heuristic + LightGBM risk models, rainfall
  roads/                    OSRM-backed road routing for wheeled units
  routers/                  risk, requests, units, dispatch, benchmark, seed, log
  ingest/                   DEM / rainfall / cyclone-track / landcover / SAR fetch scripts
apps/web/                 React operations console
docs/                     PRD · TRD · WORKFLOW · DESIGN
CLAUDE.md                 build rules — read this first
```

`packages/qubo-dispatch` imports nothing from the rest of the repo. It is published separately so anyone can use the formulation for their own dispatch problem.

---

## Running it

```bash
# API
cd services/api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt          # versions are pinned — do not upgrade
uvicorn main:app --reload

# Seed the demo
curl -X POST "localhost:8000/seed/titli?disaster_type=cyclone"

# Web
cd apps/web && npm install && npm run dev
```

No database setup is required to run the app as it stands — everything reads from in-memory stores and the precomputed risk caches committed under `services/api/data/raw/`. The system also runs with Qiskit uninstalled: it falls back to classical solvers and logs the fallback.

### Deploying

**Backend → Railway (Dockerfile), frontend → Vercel (zero-config Vite).** Full step-by-step, including the exact settings and a troubleshooting table, is in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

---

## Tests

```bash
cd packages/qubo-dispatch && pytest      # 545 tests
cd services/api && pytest                # 74 tests
```

Two in `qubo-dispatch` are release gates:
- `test_constraints.py` — 500 random instances, no assignment ever double-books a unit or a request, on any backend
- `test_fallback.py` — with Qiskit patched to fail on import, a valid assignment still comes back
