# BUILD SPEC — services/api

Implementation contract for the FastAPI service. Read `../../CLAUDE.md` first.

`schema.sql` in this directory is the runnable source of truth for the database. Do not retype it from `docs/TRD.md`.

---

## Build order

```
1. main.py + /health          → deploy to Railway, green, empty
2. routers/ with fixtures     → unblocks frontend immediately
3. risk/terrain.py            → DEM, HAND (slowest, start early)
4. roads/graph.py
5. risk/model.py
6. routers/ wired to real data
7. dispatch/orchestrator.py
8. seed/titli.py
```

Step 1 happens in hour 0–2. Step 2 returns hardcoded fixtures matching the real response models, so the frontend never waits on the backend.

---

## Layout

```
services/api/
├── schema.sql              # runnable, source of truth
├── requirements.txt        # pinned, see CLAUDE.md §3
├── main.py
├── db.py                   # supabase client, single instance
├── models.py               # all Pydantic v2 request/response models
├── risk/
│   ├── terrain.py          # DEM → HAND, slope, TWI, dist_stream
│   ├── features.py         # assemble the feature matrix
│   ├── labels.py           # Sentinel-1 SAR → binary flood mask
│   ├── model.py            # LightGBM train + predict
│   └── heuristic.py        # the fallback index
├── roads/
│   ├── graph.py            # osmnx ingest → networkx
│   └── passability.py      # water depth → edge weights
├── dispatch/
│   ├── severity.py         # Stage 04 triage
│   └── orchestrator.py     # partition → solve → route → persist
├── routers/
│   ├── risk.py  requests.py  units.py  dispatch.py
│   └── benchmark.py  log.py  seed.py
└── seed/
    └── titli.py
```

---

## `risk/terrain.py`

Runs once at seed time. Slow — start it in hour 2, not hour 10.

```python
def build_grid(bbox, cell_m=250) -> GeoDataFrame
def compute_hand(dem_path) -> np.ndarray
def compute_slope(dem_path) -> np.ndarray
def compute_twi(dem_path) -> np.ndarray
def dist_to_stream(grid, waterways) -> np.ndarray
```

HAND via `pysheds`: fill depressions → flow direction → flow accumulation → threshold to a stream network → for each cell, elevation minus the elevation of the stream cell it drains to.

**Traps:**
- `rasterio` and GDAL installs are hostile. Docker or conda, set up in hour 2. If it isn't importable by hour 4, escalate.
- DEM and grid must share a CRS. Reproject once, up front, and assert it.
- `pysheds` wants a conditioned DEM. Skipping the fill step gives HAND values that look plausible and are wrong.

Cache every intermediate raster to disk. You will re-run this and you do not want to recompute flow accumulation twice.

---

## `risk/labels.py`

Sentinel-1 SAR flood extent, post-Titli, via Microsoft Planetary Computer (free, no auth).

```python
def fetch_sar(bbox, date_range) -> xr.DataArray
def flood_mask(vv_band, threshold_db=-18) -> np.ndarray
```

Smooth water gives low VV backscatter. Threshold, then morphological opening to drop speckle.

**Hard 90-minute cap on this task.** If it hasn't produced a usable mask by then, switch to `risk/heuristic.py`, label it a heuristic in the UI, and move on. Decide that in advance so it's a decision, not a panic.

---

## `risk/model.py`

```python
def train(features, labels) -> Booster      # LightGBM binary, save models/risk_lgbm.txt
def predict(features) -> np.ndarray         # 0..1
def feature_importance() -> dict[str, float]
def band(score) -> int                      # 0..4, thresholds .2/.4/.6/.8
```

Ship feature importances to the API — the map detail panel needs the top three contributors per cell. That's the explainability story and it's half the pitch for Stage 02.

---

## `risk/heuristic.py`

The fallback. No training, works immediately.

```python
risk = 0.40*norm(1-hand) + 0.30*norm(rain_72h) + 0.15*norm(1-slope) + 0.10*norm(1-dist_stream) + 0.05*drainage_penalty
```

Return the same shape as `model.predict`, plus per-term contributions so the detail panel works identically either way.

---

## `roads/graph.py` and `passability.py`

```python
G = osmnx.graph_from_place("Srikakulam district, India", network_type="drive")
```

Persist to `road_segments`. For each edge sample DEM elevation along the geometry and store the minimum.

```python
def update_passability(risk_scores) -> None     # writes water_depth_m, passable_*
def travel_matrix(units, requests, kind) -> dict[tuple[str,str], float]
```

Impassable edges get `weight = inf` for that unit kind. Dijkstra on what remains.

**Traps:**
- Boats gain access where cars lose it. Two separate passability flags, two separate graph views.
- If no path exists, **omit the pair from the dict entirely** — do not insert `inf`. `formulation.py` treats a missing key as unreachable and skips creating the variable.
- Cache the base graph. Re-ingesting OSM per round is unusably slow.

---

## `dispatch/severity.py`

```python
severity = 0.30*norm(people) + 0.30*category_weight + 0.25*area_risk + 0.15*norm(wait_min)
# medical 1.0 · stranded 0.7 · evacuation 0.5
```

**Return all four components** and persist them to `sev_people`, `sev_category`, `sev_area_risk`, `sev_wait`. The whole argument for a formula over a model is that the officer can see why one request outranks another. If you only store the total, that argument is dead.

Normalise `people` against the current max in the open queue, not a constant.

---

## `dispatch/orchestrator.py`

```python
def run_round(backend="qaoa", timeout_s=10.0) -> DispatchRoundResult
```

1. Fetch `open` requests and `available` units
2. **Guard:** if either is empty, log and exit. Do not solve an empty problem.
3. `update_passability(current_risk)`
4. Compute severity with components
5. Build `travel_matrix`
6. `qubo_dispatch.solve_partitioned(problem, backend=backend)`
7. Persist `dispatch_rounds`, `assignments`, `benchmarks`
8. Route each assignment, store the LineString
9. Write `dispatch_log` lines
10. Realtime broadcasts automatically via Postgres replication

Target: 200 requests, 40 zones, under 5 seconds.

The unique indexes on `assignments` are your last line of defence — a double-booking that somehow escapes `validate_constraints` will fail the insert rather than reach the officer.

---

## `routers/requests.py` — offline sync

```python
POST /requests          # single, upsert on client-supplied uuid
POST /requests/sync     # bulk, list[RequestCreate], upsert
```

The client generates the UUID. **Upsert, never insert.** A replayed batch must be harmless — that's the entire conflict-resolution story, and "idempotent by client-generated UUID" is the one-sentence answer if a judge asks.

Preserve the client's `created_at`; set `synced_at` server-side. They will differ, and the gap is what proves the offline path worked.

---

## `seed/titli.py`

```python
POST /seed/titli
```

- IMD track: landfall at Gollapadu, Vajrapukotturu mandal, 11 Oct 2018, roughly 04:30–05:30 IST
- Rainfall from NASA POWER for the actual dates
- 15 units at real facility coordinates from OSM (district hospital, fire stations)
- ~200 synthetic requests at real village coordinates, **weighted toward genuinely low-lying areas per the computed HAND raster** — not uniformly random. Clustering in real floodplains is what makes the demo look like a disaster instead of noise.
- Categories mixed roughly 20 % medical, 50 % stranded, 30 % evacuation

Also seed a scripted road-closure event the demo can trigger on cue. That's beat five, the peak of the demo, and it must be deterministic — not something you hope fires.

---

## Failure protocol

| If | Then |
|---|---|
| GDAL/rasterio won't install by H4 | Docker image with GDAL preinstalled. Do not keep fighting pip. |
| SAR labels exceed 90 min | `risk/heuristic.py`. State it's a heuristic. Move on. |
| Road graph too slow per round | Precompute the full travel matrix at seed time, patch only flooded edges per round |
| Dispatch exceeds 5 s | Reduce zone size to 4 requests, raise worker count |
