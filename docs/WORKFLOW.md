# WORKFLOW — PRAHARI

System flows, state machines, and the 24-hour build order.

---

## 1. Core loop

```
   rainfall + terrain
          │
          ▼
   ┌─────────────┐
   │ RISK MODEL  │──────────────► risk map (F1)
   └──────┬──────┘
          │ risk_score per cell
          │
          ├────────────────────────┐
          ▼                        ▼
   ┌─────────────┐         ┌──────────────┐
   │ ROAD GRAPH  │         │   TRIAGE     │
   │ passability │         │  severity    │
   └──────┬──────┘         └──────┬───────┘
          │ travel_time_ij        │ severity_j
          └───────────┬────────────┘
                      ▼
              ┌───────────────┐
              │  PARTITION    │  ≤5 requests/zone
              └───────┬───────┘
                      ▼
         ┌─────────────────────────┐
         │  QUBO per zone (par.)   │
         └────────────┬─────────────┘
                      ▼
         ┌─────────────────────────┐
         │ ROUTER                  │
         │ qaoa → anneal → greedy  │
         └────────────┬─────────────┘
                      ▼
              ┌───────────────┐
              │  VALIDATE     │──── hard gate, nothing passes unvalidated
              └───────┬───────┘
                      ▼
              assignments + routes
                      │
                      ▼
        ┌───────────────────────────┐
        │ road floods → recompute   │────► loop back to ROAD GRAPH
        └───────────────────────────┘
```

The loop back at the bottom is the point. Travel costs change as the flood evolves, which forces re-optimization, which is why the dispatch engine exists at all.

---

## 2. Request lifecycle

```
                 ┌──────────┐
   citizen ─────►│ QUEUED   │  (IndexedDB, offline only)
                 └────┬──────┘
                      │ connectivity restored
                      ▼
                 ┌──────────┐
                 │  OPEN    │────────────────┐
                 └────┬──────┘               │
                      │ dispatch round        │ unit becomes unavailable
                      ▼                       │
                 ┌──────────┐                 │
                 │ ASSIGNED │◄────────────────┘
                 └────┬──────┘
                      │ responder acknowledges
                      ▼
                 ┌─────────────┐
                 │ IN_PROGRESS │
                 └────┬─────────┘
                      ▼
                 ┌──────────┐        ┌───────────┐
                 │ RESOLVED │        │ CANCELLED │
                 └──────────┘        └───────────┘
```

Only `OPEN` requests enter a dispatch round. `ASSIGNED` requests return to `OPEN` if their unit goes offline — the next round re-plans them automatically.

---

## 3. Unit lifecycle

```
AVAILABLE ──► ASSIGNED ──► EN_ROUTE ──► RETURNING ──► AVAILABLE
     ▲                                                    │
     └──────────────────► OFFLINE ◄─────────────────────────┘
```

Only `AVAILABLE` units enter a dispatch round. This is what makes the rolling horizon work: each round plans with whatever is free right now, rather than trying to schedule the whole event up front.

---

## 4. Dispatch round — step by step

1. **Gather.** Fetch `OPEN` requests and `AVAILABLE` units.
2. **Guard.** If either is empty, log and exit. Do not solve an empty problem.
3. **Refresh roads.** Recompute `water_depth_m` from current risk, update passability flags.
4. **Score.** Compute severity for every open request, with components.
5. **Partition.** Constrained k-means → zones of ≤ 5 requests, ≤ 4 units each.
6. **Formulate.** Build one QUBO per zone. Auto-tune λ from the objective bound.
7. **Solve in parallel.** `ProcessPoolExecutor`, one zone per worker, through the router chain.
8. **Validate.** Reject any assignment that double-books. On rejection, fall through to the next solver.
9. **Merge.** Combine zone results into one plan.
10. **Route.** Shortest path per assignment over the flood-aware graph.
11. **Persist.** Write `dispatch_rounds`, `assignments`, `benchmarks`, and log lines.
12. **Broadcast.** Supabase Realtime pushes to every connected client.

Target: 200 requests across 40 zones, under 5 seconds end to end.

---

## 5. Offline sync

```
OFFLINE                          ONLINE
   │                                │
   │ user submits                   │
   ▼                                │
generate uuid (client)              │
   │                                │
   ▼                                │
IndexedDB {synced: false}           │
   │                                │
   │ ◄── connectivity restored ─────┤
   ▼                                │
POST /requests/sync (batch) ────────►│
   │                                │
   │        server upserts on uuid  │
   │        ◄──── 200 + ids ────────┤
   ▼                                │
mark synced: true                   │
   │                                │
   ▼                                │
Realtime pushes to dashboard ◄───────┘
```

Idempotent by construction: the client generates the UUID, the server upserts on it. A replayed batch is harmless. If a judge asks about conflict resolution, that sentence is the whole answer.

---

## 6. Solver fallback

```
        ┌─────────┐
        │  QAOA   │  timeout 10s
        └────┬─────┘
      ok ◄────┤──── exception / timeout / invalid
             │              │
             ▼              ▼
        ┌─────────┐   ┌──────────────┐
        │ RETURN  │   │  ANNEALING   │
        └─────────┘   └──────┬────────┘
                    ok ◄──────┤────── fail
                             │         │
                             ▼         ▼
                        ┌─────────┐ ┌─────────┐
                        │ RETURN  │ │ GREEDY  │
                        └─────────┘ └────┬─────┘
                                        │
                                        ▼
                                   ┌─────────┐
                                   │ RETURN  │
                                   └─────────┘
```

Every fallback is logged and surfaced in the UI as `fell_back: true`. Do not hide it — visible degradation is a feature, and it proves the architecture claim.

---

## 7. Build order — 24 hours, 4 people

Roles: **A** backend/data · **B** frontend/map · **C** quantum/optimization · **D** integration/demo

### H0–2 · Foundation
- **All:** repo, branch protocol, `.env`
- **A:** Supabase project, run schema, PostGIS enabled
- **B:** Vite app, Tailwind with locked tokens, deploy to Vercel — **empty but green**
- **C:** isolated venv, pin Qiskit versions, commit lockfile, `import qiskit_aer` succeeds
- **D:** FastAPI skeleton, deploy to Railway — **empty but green**

> Deployment at hour 20 is how teams die. Both surfaces are live before any feature exists.

### H2–6 · Parallel tracks
- **A:** DEM ingest, HAND via pysheds, Overpass facility pull, Open-Meteo wiring
- **B:** MapLibre with PMTiles, risk choropleth against mock data, layer toggles
- **C:** `formulation.py`, `penalties.py`, greedy + annealing solvers, **against mock data only** — no waiting on the backend
- **D:** API contracts as Pydantic stubs returning fixtures, so B and C are never blocked

### H6–10 · First real signal
- **A:** train LightGBM (or ship the physical index if labels stall past the 90-minute cap), write `risk_cells`
- **B:** wire the real risk endpoint, build the cell detail panel with feature importances
- **C:** QAOA solver, warm start from greedy, `test_constraints.py` green
- **D:** road graph ingest, passability computation

### H10–14 · The engine
- **A:** severity scoring, request CRUD, unit CRUD
- **B:** request intake form, dispatch view, unit panel
- **C:** partitioner, router, fallback chain, `test_fallback.py` green
- **D:** dispatch orchestration endpoint, routing over the flood-aware graph

### H14–17 · Offline
- **B:** service worker, PMTiles cache, IndexedDB queue, background sync
- **A:** `/requests/sync` bulk endpoint, upsert semantics
- **C:** benchmark harness across all four solvers
- **D:** Realtime subscriptions on the dashboard

### H17–20 · Proof
- **C+D:** benchmark table with real measured numbers — **including QAOA losses**
- **C:** publish `qubo-dispatch` to GitHub, MIT license, README with a working example
- **B:** dispatch log panel, the append-only ops ledger
- **A:** seed script hardening

### H20–22 · The scenario
- **All:** load Titli. Real coordinates, real dates, ~200 requests, 15 units.
- **D:** script the demo arc, including the road-flood re-solve
- **B:** final pass against `DESIGN.md` — hunt and remove any gradient, any radius above 2px, any stray colour

### H22–24 · Freeze
- Code freeze. No new features. Bugs only.
- Rehearse the demo four times, start to finish
- Record a backup video
- Two people rehearse the quantum Q&A: penalty weights, ansatz depth, qubit count, and why each

---

## 8. Demo script — 5 minutes

| Time | Beat | Say |
|---|---|---|
| 0:00 | Risk map, Srikakulam, 11 Oct 2018 | "Cyclone Titli. Everyone here remembers it." |
| 0:40 | Click a cell, show feature importances | "Height above nearest drainage dominates. The model is explainable because an emergency officer will not act on a number they cannot interrogate." |
| 1:10 | Requests arrive, triage ranks them | "Every project stops at the map. A map does not rescue anyone." |
| 1:40 | Run dispatch, zones partition and solve | "200 requests, 40 zones, solved in parallel. Each zone is 20 qubits regardless of how big the disaster gets — we scale horizontally, not by adding qubits." |
| 2:30 | Benchmark table | "OR-Tools matches or beats QAOA at this scale. We show you that rather than hiding it. What we built is the formulation — that is the part that does not change when the hardware does." |
| 3:10 | Offline: throttle, submit, reconnect, land | "Degraded network is the normal case in a flood, not the edge case." |
| 3:40 | **Flood a road, re-solve, assignments change** | "This is why the engine has to exist. The cost matrix changes as the water moves." |
| 4:20 | Dispatch log | "Append-only. Every decision is auditable after the event." |
| 4:40 | Close | "Everyone predicts the flood. We also decide who gets rescued first." |

---

## 9. Failure protocol

| If | Then |
|---|---|
| Qiskit is not working by H12 | Ship classical-only, reframe as "quantum-ready formulation, solver not yet wired". Losing the differentiator beats losing the product. |
| Sentinel-1 labels exceed 90 min | Switch to the physical index. Say it is a heuristic. Move on. |
| Deploy breaks after freeze | Demo from localhost. Have it running before you walk up. |
| Venue wifi dies | Backup video. Have it on two laptops and one phone. |
| A judge challenges the quantum claim | Agree with them. "You are right that it does not beat classical today. That is what our benchmark shows. The contribution is the formulation." Never defend a claim you did not make. |
