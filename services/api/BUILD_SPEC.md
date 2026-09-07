# BUILD SPEC — services/api

Implementation contract for the backend. Read `../../CLAUDE.md` and `../../docs/MIGRATION.md` first.

`schema.sql` in this directory is runnable and is the source of truth for the database. Do not retype DDL from the docs.

---

## Build order

Each step leaves the service working. Do not skip ahead.

```
1. config.py + swap region      -> verify carried terrain pipeline runs on Aizawl
2. schema.sql applied            -> additive, nothing dropped (once a DB exists)
3. terrain/ extended             -> aspect sin/cos, curvature, road cut
4. ml/ (see docs/TRAINING.md)    -> susceptibility + trigger
5. routers/ with fixtures        -> unblocks both clients immediately
6. roads/ + isolation            -> the differentiating feature, build early
7. reports/                      -> citizen intake + clustering, BEFORE the citizen app
8. alerts/                       -> CAP generation
9. dispatch/ rewire              -> add isolation term
10. insar/ runtime service       -> reads pre-computed data only
```

**Step 1 is the day-1 proof.** If the carried terrain pipeline produces a slope raster for Aizawl without code changes beyond the region constant, the migration thesis holds and everything after is incremental. Verify it before anything else.

**Step 6 is not "wire up the carried module" — it is new work.** `docs/MIGRATION.md` §2 corrects an earlier draft that claimed the road graph carries over; it does not. Build it early anyway, because isolation scoring — and the deterministic demo road-block trigger that depends on it — is the differentiator and needs days of headroom to test, not hours.

**Step 7 comes before the citizen app is built**, not after — the client is written against a real endpoint.

---

## Layout

```
services/api/
├── schema.sql              # runnable, source of truth
├── config.py               # REGION constant — single definition
├── main.py
├── db.py
├── models.py               # all Pydantic v2 models
├── ingest/                 # see docs/DATA.md
├── terrain/                # carried, extended
├── ml/                     # see docs/TRAINING.md
├── insar/
│   ├── pipeline/           # OFFLINE ONLY — never imported by the API
│   ├── load.py             # one-time loader into deformation_*
│   └── service.py          # runtime: reads, classifies alert_state
├── roads/
│   ├── graph.py            # NEW — OSM ingest -> networkx
│   ├── passability.py      # NEW — blockage tracking
│   └── isolation.py        # NEW — connected components, settlement scoring
├── reports/
│   ├── intake.py
│   ├── cluster.py
│   └── media.py
├── alerts/
│   ├── cap.py
│   ├── geofence.py
│   └── templates/{en,hi,as}.json
├── dispatch/               # carried, severity rewired
└── routers/
```

---

## 1. `config.py`

```python
REGION = {
    "name": "Aizawl district, Mizoram",
    "bbox": {"west": 92.55, "south": 23.55, "east": 93.05, "north": 24.05},
    "grid_m": 100,
    "crs": "EPSG:4326",
    "utm": "EPSG:32646",
    "hq": (23.7271, 92.7176),      # Aizawl — isolation scoring anchor
}
LANGUAGES = ["en", "hi", "as"]   # English, Hindi, Assamese — no others generated
```

Single definition. Every module imports it. Never hardcode coordinates twice.

**This module did not exist before the pivot.** `ingest/config.py` and `risk/features.py` each hardcoded their own, disagreeing, Srikakulam-specific bbox — both get refactored to import from here instead.

---

## 2. `terrain/` — carried, extended

The existing DEM pipeline runs on the new bbox with only the region-constant swap. Add these derivations:

```python
def aspect_components(dem) -> tuple[np.ndarray, np.ndarray]:
    """Return (sin, cos) of aspect. NEVER return raw degrees —
    aspect is circular and 359deg is adjacent to 1deg."""

def curvature(dem) -> tuple[np.ndarray, np.ndarray]:
    """Plan and profile curvature. Concave profile concentrates
    subsurface flow and is a strong landslide predictor."""

def ls_factor(slope, flow_acc) -> np.ndarray

def road_proximity(grid, roads) -> tuple[np.ndarray, np.ndarray]:
    """dist_road_m, and is_cut_slope = (dist < 50) & (slope > 25).
    Encodes the 'unplanned hill cutting' driver named in the PS."""
```

**Traps:**
- Reproject once, up front, and assert the CRS. DEM and grid must match.
- `pysheds` needs a conditioned DEM — skipping the depression fill produces HAND values that look plausible and are wrong.
- Cache every intermediate raster. Flow accumulation is slow and you will re-run this.
- At 100 m over this bbox you have roughly 250k cells. Vectorise; do not loop.

---

## 3. `insar/` — the critical separation

### `pipeline/` — offline, never imported by the API

Documented scripts for ISCE2 -> MintPy -> export. These run in a **separate conda environment**. If `isce2` or `mintpy` appears in `requirements.txt`, the deploy will break.

### `load.py` — one-time

Reads MintPy output, filters, writes to `deformation_points` and `deformation_series`.

```python
COHERENCE_MIN = 0.30   # discard below this, no exceptions
```

Vegetated hillslopes decorrelate badly and low-coherence points produce confident-looking nonsense. This is the fastest way to embarrass yourself in front of a geologist.

### `service.py` — runtime

Reads only. Never processes.

```python
def classify_state(velocity, acceleration) -> str:
    if abs(velocity) < 5.0:
        return "stable"
    if acceleration < ACCEL_THRESHOLD:
        return "creeping"
    return "accelerating"
```

**Acceleration is the warning signal, not velocity.** Many hillslopes creep steadily for years without failing; onset of acceleration is what precedes failure. Surface this distinction in the API response and make the UI show it — it is the difference between flagging every steep slope and flagging the one that is about to go.

`GET /insar/corridors` returns the processed boundary. The UI draws it, and outside it the layer is empty and says so. **Never interpolate across unprocessed area.**

---

## 4. `roads/` and `roads/isolation.py` — the differentiator, build early

```python
def compute_isolation() -> dict[int, float]:
    """
    1. Build the road graph, remove edges where blocked = true
    2. networkx.connected_components
    3. For each settlement:
         - which component it is in
         - component size (settlements + population)
         - whether a path to REGION['hq'] survives
    4. Score:
         no path to HQ            -> 1.0
         path exists, small comp  -> 0.3..0.7 by inverse component size
         path exists, large comp  -> 0.0..0.3
    5. Write settlements.isolated, isolation_score, component_size, path_to_hq
    """
```

Recompute on every road status change and broadcast via Realtime.

**Why this matters, and it is worth understanding rather than just implementing:** in a flood, people can often self-evacuate. On a ridge, one blocked road removes every route out. Isolation is therefore an independent axis of urgency, not a proxy for hazard exposure — a settlement of forty with no route can legitimately outrank a larger one that still has a road. It is a direct consequence of this hazard's mechanism, and most teams will not have it.

Blockage has three sources — `predicted` (from risk), `reported` (citizen or field), `confirmed` (admin). Store the source and display it. An officer must know whether a road is actually blocked or only modelled as likely.

**Build the deterministic demo road-block trigger here, as soon as this module exists** — a named ridge segment (`PATCH /roads/{id}` with `block_reason=confirmed`) that isolates 2-3 known settlements. This is the peak of the demo (`docs/WORKFLOW.md` §7, beat 3:10) and it must be tested days before rehearsal. Do not defer this to `seed/demo.py` at the end of the build.

---

## 5. `reports/` — built before the citizen app

```
POST  /reports              # single, upsert on client uuid
POST  /reports/sync         # bulk offline flush
GET   /reports?status=&bbox=&cluster_id=
PATCH /reports/{id}         # verify | dismiss | duplicate
POST  /reports/{id}/media   # multipart upload
```

### Clustering — `cluster.py`

```python
CLUSTER_RADIUS_M = 100
CLUSTER_WINDOW_MIN = 60
```

Ten photographs of one slope failure must arrive as one incident. An unclustered queue is unusable within minutes of a real event, and this is not optional polish.

On insert: find an existing cluster within radius and window, else create one. Update `report_count`, `last_seen`, `dominant_kind`.

### Idempotency

Client generates the UUID, server upserts on it. Replayed batches are harmless. Preserve the client's `created_at`; set `synced_at` server-side — the gap between them is what proves the offline path worked, so surface it in the UI.

### Privacy

Store `reporter_hash` — a salted hash of a device identifier. **Never store identity.** Strip EXIF beyond coordinates before persisting media. State this unprompted in the pitch; a ministry panel will care about it.

### Media

Supabase Storage. Generate a thumbnail on upload — the admin queue must not load full-resolution photographs. Retry media independently of metadata: a report whose photo upload failed should still sync its metadata, with the media following later.

---

## 6. `alerts/`

```python
def generate_cap(severity, geofence, languages, headline, instruction) -> str
def evaluate_geofences(lat, lon) -> list[Alert]
```

CAP (Common Alerting Protocol) is the international standard Indian agencies already use, so this interoperates with existing infrastructure rather than competing with it. Say that.

Templates in `templates/{lang}.json`, keyed by severity band, for `en`, `hi`, `as` only — see `config.py`'s `LANGUAGES`. **Never build messages by string concatenation** — it makes translation impossible and produces ungrammatical output in every language that is not English.

**Delivery is out of scope.** Generate the payload, display it, say so plainly.

Geo-fences are cached on the citizen client and evaluated there, so alerts work with no signal. The moment connectivity fails is exactly when an alert matters most.

---

## 7. `dispatch/` — carried, rewired

```
sigma = 0.28*persons + 0.28*category + 0.22*area_risk
      + 0.12*wait + 0.10*isolation
```

Persist all five components. `sev_isolation` comes from `settlements.isolation_score` via `requests.settlement_id`.

`packages/qubo-dispatch` is unchanged. **Do not modify it.** Default backend `ortools`; QAOA remains available behind the router.

UI treatment: one line, `solver: ortools · formulation: QUBO · quantum-ready`. No heading, no badge, no nav item.

---

## 8. API surface

```
GET   /health

GET   /risk/cells?bbox=&band_min=        # GeoJSON, includes provenance
GET   /risk/cell/{id}                    # score + top-3 attributions

GET   /insar/corridors
GET   /insar/points?corridor=&state=
GET   /insar/series/{point_id}

GET   /roads?bbox=&blocked=
PATCH /roads/{id}                        # block | clear, with source
GET   /settlements?isolated=

POST  /reports  ·  POST /reports/sync
GET   /reports  ·  PATCH /reports/{id}
POST  /reports/{id}/media
GET   /clusters?bbox=

POST  /alerts/generate
GET   /alerts/active?lat=&lon=
GET   /alerts/geofences                  # for client-side caching

POST  /requests  ·  POST /requests/sync
GET   /requests?status=
POST  /dispatch/solve
GET   /benchmark/results

GET   /log?since=
POST  /seed/demo
```

All responses Pydantic v2. Errors RFC 7807.

---

## 9. Seed — `seed/demo.py`

```
POST /seed/demo
```

- Real Aizawl settlement coordinates from OSM
- Real rainfall for a chosen monsoon window
- Deformation from the actual processed corridor — **real measured values only**
- ~30 citizen reports, clustered around 3-4 incident locations, some with media
- 8 response units at real facility positions
- References the same road blockage tested in `roads/isolation.py` (§4) — this endpoint re-seeds the scenario for rehearsal, it does not implement the trigger for the first time.

---

## 10. Failure protocol

| If | Then |
|---|---|
| GDAL/rasterio will not install | Docker with GDAL preinstalled. Stop fighting pip. |
| Terrain pipeline fails on Aizawl | Escalate immediately — the whole migration thesis rests on it |
| InSAR incomplete by end of day 4 | Load whatever processed. One pair with a velocity map is real data. |
| Isolation is slow at scale | Precompute components per road-state hash and cache |
| Clustering misses duplicates | Widen radius before widening the time window; spatial error dominates |
