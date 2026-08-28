# TRD — PRAHARI

Technical specification. Pairs with `CLAUDE.md` (build rules) and `docs/PRD.md` (product scope).

---

## 1. Architecture

```
┌───────────────────────────────────────────────────────────┐
│  apps/web  ·  Vite + React + MapLibre + Service Worker    │
│  /map   /dispatch   /requests   /benchmark                 │
└──────────────┬───────────────────────────────────────────┘
               │ REST + Supabase Realtime
┌──────────────┼───────────────────────────────────────────┐
│  services/api  ·  FastAPI                                  │
│  ┌────────────┬─────────────┬────────────┬────────────┐  │
│  │ risk/      │ roads/      │ dispatch/  │ seed/      │  │
│  │ LightGBM   │ OSM graph   │ orchestr.  │ Titli      │  │
│  └────────────┴─────────────┴─────┬──────┴────────────┘  │
└─────────────────────────────────────┼─────────────────────┘
                                     │
              ┌──────────────────────┼─────────────────┐
              │  packages/qubo-dispatch  (standalone)   │
              │  formulation → penalties → partition    │
              │  → router → {qaoa | anneal | ortools |  │
              │               greedy}                    │
              └──────────────────────┬─────────────────┘
                                     │
              ┌──────────────────────┼─────────────────┐
              │  Supabase · Postgres 15 + PostGIS       │
              └──────────────────────────────────────────┘
```

`packages/qubo-dispatch` imports nothing from the rest of the repo. It is MIT-licensed and publishable on its own.

---

## 2. Data model

PostGIS, SRID 4326 throughout.

```sql
create extension if not exists postgis;

-- Terrain and risk, one row per grid cell
create table risk_cells (
  id            bigserial primary key,
  geom          geometry(Polygon, 4326) not null,
  centroid      geometry(Point, 4326) not null,
  elevation_m   real,
  hand_m        real,              -- height above nearest drainage
  slope_deg     real,
  twi           real,              -- topographic wetness index
  dist_stream_m real,
  soil_drainage smallint,
  landcover     smallint,
  risk_score    real,              -- 0..1, model output
  risk_band     smallint,          -- 0 normal, 1 watch, 2 alert, 3 warning, 4 severe
  computed_at   timestamptz default now()
);
create index on risk_cells using gist (geom);
create index on risk_cells using gist (centroid);

-- Rescue requests
create table requests (
  id            uuid primary key,        -- client-generated, makes sync idempotent
  location      geometry(Point, 4326) not null,
  people_count  smallint not null check (people_count > 0),
  category      text not null check (category in ('medical','stranded','evacuation')),
  note          text,
  status        text not null default 'open'
                check (status in ('open','assigned','in_progress','resolved','cancelled')),
  severity      real,                    -- computed, 0..1
  created_at    timestamptz not null,    -- client clock, may precede synced_at
  synced_at     timestamptz default now(),
  resolved_at   timestamptz
);
create index on requests using gist (location);
create index on requests (status, severity desc);

-- Rescue units
create table units (
  id            uuid primary key,
  label         text not null,           -- 'Boat 03', 'Ambulance 07'
  kind          text not null check (kind in ('boat','ambulance','truck','team')),
  capacity      smallint not null,
  position      geometry(Point, 4326) not null,
  status        text not null default 'available'
                check (status in ('available','assigned','en_route','returning','offline')),
  home_base     geometry(Point, 4326)
);
create index on units using gist (position);

-- Road segments with dynamic passability
create table road_segments (
  id            bigserial primary key,
  osm_id        bigint,
  geom          geometry(LineString, 4326) not null,
  road_class    text,
  base_speed_kmh real,
  min_elev_m    real,
  water_depth_m real default 0,
  passable_car  boolean default true,    -- water_depth_m < 0.3
  passable_boat boolean default true
);
create index on road_segments using gist (geom);

-- One dispatch solve
create table dispatch_rounds (
  id            uuid primary key,
  started_at    timestamptz default now(),
  zone_count    smallint,
  request_count smallint,
  unit_count    smallint,
  backend       text,                    -- qaoa | annealing | ortools | greedy
  fell_back     boolean default false,
  objective     real,
  solve_ms      integer
);

create table assignments (
  id            uuid primary key,
  round_id      uuid references dispatch_rounds(id),
  unit_id       uuid references units(id),
  request_id    uuid references requests(id),
  zone_id       smallint,
  travel_s      integer,
  route         geometry(LineString, 4326),
  created_at    timestamptz default now()
);

-- Benchmark results, one row per solver per instance
create table benchmarks (
  id            bigserial primary key,
  round_id      uuid references dispatch_rounds(id),
  backend       text not null,
  objective     real,
  solve_ms      integer,
  constraints_valid boolean,
  qubit_count   smallint,
  notes         text
);

-- Append-only operations log (the UI signature element)
create table dispatch_log (
  id            bigserial primary key,
  at            timestamptz default now(),
  channel       text not null,           -- risk | intake | dispatch | road | system
  severity      smallint default 0,
  message       text not null
);
```

---

## 3. Risk model — Problem A

### Features

Computed once at seed time into `risk_cells`. Grid resolution: 250 m.

| Feature | Source | Notes |
|---|---|---|
| `elevation_m` | Copernicus DEM 30 m | resample to grid |
| `hand_m` | derived via `pysheds` | **strongest single flood predictor** — do not skip |
| `slope_deg` | derived from DEM | |
| `twi` | `ln(upslope_area / tan(slope))` | |
| `dist_stream_m` | OSM `waterway=*` | nearest-neighbour distance |
| `soil_drainage` | SoilGrids / FAO | ordinal class |
| `landcover` | ESA WorldCover | categorical, one-hot |
| `rain_24h`, `rain_72h`, `rain_7d` | Open-Meteo + NASA POWER | joined at inference, not stored per cell |

### Labels

**Preferred:** Sentinel-1 SAR flood extent for post-Titli dates via Microsoft Planetary Computer. SAR penetrates cloud, which optical imagery cannot during a cyclone. Threshold VV backscatter to a binary flood mask, rasterise to the grid.

**Fallback if this exceeds 90 minutes:** ship a weighted physical index instead of ML, and label it as a heuristic in the UI.

```
risk = 0.40·norm(1 − hand) + 0.30·norm(rain_72h) + 0.15·norm(1 − slope)
     + 0.10·norm(1 − dist_stream) + 0.05·drainage_penalty
```

A transparent index you can explain beats a black box you cannot. State the choice honestly either way.

### Model

LightGBM binary classifier, `predict_proba` → `risk_score`. Not deep learning: faster to train, better on tabular data, and it yields feature importances, which an emergency officer will actually need in order to trust the output.

Bands: `[0, .2) normal · [.2, .4) watch · [.4, .6) alert · [.6, .8) warning · [.8, 1] severe`

Persist `models/risk_lgbm.txt` and the feature-importance JSON. Ship importances to the map detail panel.

---

## 4. Road graph

```python
G = osmnx.graph_from_place("Srikakulam district, India", network_type="drive")
```

For each edge: sample DEM elevation, take the minimum along the segment, look up the predicted water depth from the risk raster.

```
passable_car  = water_depth_m < 0.30
passable_boat = True                      # boats gain access where cars lose it
travel_time_s = length_m / effective_speed
```

Impassable edges get weight `inf` for that unit kind. Recompute on each dispatch round. Route with `networkx.shortest_path(weight="travel_time_s")`.

**This is what makes the problem disaster-specific rather than generic assignment.** The cost matrix changes as the flood evolves, which forces re-optimization, which is why the dispatch engine has to exist at all. Make sure the pitch draws that line.

---

## 5. Dispatch engine — Problem B

### 5.1 Severity

```
severity = w1·norm(people_count)
         + w2·category_weight          # medical 1.0, stranded 0.7, evacuation 0.5
         + w3·risk_score_at_location
         + w4·norm(minutes_waiting)

weights: w1=0.30, w2=0.30, w3=0.25, w4=0.15
```

Return the four components alongside the total. The officer must be able to see why one request outranks another.

### 5.2 Partition

Constrained k-means on request coordinates.

- Target ≤ 5 requests per zone
- `k = ceil(open_requests / 5)`
- Assign units to zones by nearest available unit to zone centroid, cap 4 per zone
- Solve all zones in parallel via `concurrent.futures.ProcessPoolExecutor`

**Known limitation, state it before a judge finds it:** a unit near a zone boundary may be better used in the neighbouring zone. We accept boundary suboptimality in exchange for constant-size subproblems, and re-partition every round so the error does not accumulate.

### 5.3 QUBO

Variable `x[i][j] = 1` if unit *i* → request *j*.

```
H_cost    = -Σ_ij (severity_j · people_j) · x_ij  +  α · Σ_ij travel_norm_ij · x_ij
H_request = λ₁ · Σ_j Σ_{i<i'} 2 · x_ij · x_i'j        # at most one unit per request
H_unit    = λ₂ · Σ_i Σ_{j<j'} 2 · x_ij · x_ij'        # at most one request per unit
H         = H_cost + λ₁·H_request + λ₂·H_unit
```

**Use at-most-one, not exactly-one.** The textbook `(Σx − 1)²` penalty forces exactly one assignment per request. In a disaster there are more requests than units, making that infeasible — the solver returns garbage. The `y(y−1) = 0` expansion above reduces to pairwise conflict terms only, with no slack variables and no extra qubits.

Normalise both objective terms to [0,1] before combining. `α = 0.3`.

### 5.4 Penalties

Computed at runtime in `penalties.py`, never hardcoded:

```
bound = max_j(severity_j · people_j) + α · max_ij(travel_norm_ij)
λ₁ = λ₂ = 1.2 · bound
```

Why 1.2 and not 10: the penalty must exceed the maximum objective gain from violating the constraint, or the optimizer will happily break it. But oversized penalties flatten the energy landscape and stall QAOA's classical optimizer, because every feasible solution starts to look identical. 1.2 is the smallest safe margin.

### 5.5 Solvers

All implement the same protocol:

```python
class Solver(Protocol):
    name: str
    def solve(self, qubo: QUBO, timeout_s: float) -> Assignment: ...
```

| Backend | Implementation | Notes |
|---|---|---|
| `qaoa` | Qiskit Aer, `p=3`, COBYLA, 1024 shots | warm-started from greedy; take the **best** measured bitstring, not the mean |
| `annealing` | pure-Python simulated annealing | geometric cooling, no dependencies |
| `ortools` | OR-Tools CP-SAT | the honest production baseline |
| `greedy` | severity-descending, nearest available unit | stdlib only, must never fail |

**Qubit budget.** Aer statevector: 24 qubits ≈ 268 MB, 30 qubits ≈ 17 GB and the process dies. Cap zones at 24 variables; target 4 × 5 = 20. If more headroom is needed, switch the Aer method to `matrix_product_state`, which handles more qubits while entanglement stays low.

### 5.6 Router and fallback

```python
def solve(problem, backend="qaoa", timeout_s=10.0) -> DispatchResult:
    chain = {"qaoa":      [qaoa, annealing, greedy],
             "annealing": [annealing, greedy],
             "ortools":   [ortools, greedy],
             "greedy":    [greedy]}[backend]
    for solver in chain:
        try:
            result = solver.solve(problem, timeout_s)
            if validate_constraints(result):
                return result.with_meta(backend=solver.name,
                                        fell_back=solver is not chain[0])
        except Exception:
            log.warning("solver %s failed, falling through", solver.name)
    raise RuntimeError("greedy failed — this is a bug, greedy cannot fail")
```

`validate_constraints` is the gate. Nothing leaves the module unvalidated.

---

## 6. API

All responses are Pydantic v2 models. Errors: RFC 7807 problem+json.

```
GET  /health

GET  /risk/cells?bbox=&band_min=          → risk grid as GeoJSON
GET  /risk/cell/{id}                      → score + top-3 feature contributions

POST /requests                            → create (idempotent on client uuid)
GET  /requests?status=&limit=             → list, severity-ordered
PATCH /requests/{id}                      → status transition
POST /requests/sync                       → bulk offline flush, idempotent

GET  /units
PATCH /units/{id}                         → status / position

POST /dispatch/solve                      → {backend?, timeout_s?}
                                          → zones, assignments, routes, meta
GET  /dispatch/rounds/{id}

POST /benchmark/run                       → runs all four solvers on one instance
GET  /benchmark/results?round_id=

GET  /log?since=                          → dispatch log tail
POST /seed/titli                          → load the demo scenario
```

**Realtime.** Supabase channels on `requests`, `assignments`, `dispatch_log`. Frontend subscribes; no polling.

---

## 7. Offline layer

- **Service worker:** Workbox. Precache the app shell. `NetworkFirst` for API GETs, `CacheFirst` for tiles.
- **Tiles:** PMTiles, single file, MapLibre reads natively. Srikakulam z10–14 ≈ 30–80 MB. Do not attempt to cache beyond the district.
- **Queue:** IndexedDB via `idb`. Store `{id: uuid(), payload, created_at, synced: false}`. The client generates the UUID, which makes sync idempotent — replays are harmless.
- **Sync:** Background Sync API. iOS Safari does not support it — fall back to an `online` event listener plus a 30-second interval retry.
- **Conflict resolution:** client UUID is the primary key. Server upserts. No conflicts by construction.

Demo it: devtools → offline → submit → show queued → back online → show it land on the dashboard. Ten seconds, and it is the most tangible thing you will show.

---

## 8. Tests

```
packages/qubo-dispatch/tests/
├── test_constraints.py   # 500 random instances, no double-booking, any backend
├── test_fallback.py      # Qiskit import raises → still returns valid assignment
├── test_penalties.py     # λ ≥ bound holds across random instances
└── test_partition.py     # every request lands in exactly one zone, sizes ≤ cap
```

`test_constraints.py` and `test_fallback.py` are release gates. Do not demo without them green.

---

## 9. Environment

```
# services/api/requirements.txt — pin exactly
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
supabase==2.31.0  # bumped from 2.11.0: that version rejects Supabase's
                  # newer sb_publishable_/sb_secret_ key format (JWT-shape
                  # regex validation) - see services/api/requirements.txt
lightgbm==4.5.0
scikit-learn==1.6.0
rasterio==1.4.3
pysheds==0.4
osmnx==2.0.1
networkx==3.4.2
ortools==9.11.4210
qiskit==1.2.4
qiskit-aer==0.15.1
qiskit-optimization==0.6.1
```

Qiskit and GDAL are the two things that will eat your night. Set both up in hour 1–2, in a Docker or conda environment, and commit the lockfile before writing a line of feature code.

Deploy: FastAPI → Railway, web → Vercel, DB → Supabase. All three green and empty before hour 2.
