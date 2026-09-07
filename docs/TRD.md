# TRD — Q-ResQ NER

Technical specification. Pairs with `CLAUDE.md` (rules) and `docs/MIGRATION.md` (what carries).

---

## 1. Architecture

```
┌───────────────────────┐   ┌───────────────────────────┐
│  apps/citizen         │   │  apps/admin               │
│  PWA + Capacitor      │   │  Desktop console          │
│  report · alerts ·    │   │  risk · deformation ·     │
│  offline queue        │   │  triage · roads ·         │
│                       │   │  dispatch · ledger        │
└──────────┬────────────┘   └────────────┬───────────────┘
           │      packages/ui (shared)    │
           └──────────────┬────────────────┘
                          │ REST + Realtime
           ┌──────────────┼───────────────────────────────┐
           │  services/api  ·  FastAPI                    │
           │  terrain · risk · insar · roads ·             │
           │  reports · alerts · dispatch                  │
           └──────────────┬───────────────────────────────┘
                          │
        ┌──────────────────┼──────────────────┐
        │  packages/qubo-dispatch (carried)   │
        │  classical today, quantum-ready     │
        └──────────────────┬──────────────────┘
                          │
        ┌──────────────────┼──────────────────┐
        │  Supabase · Postgres 15 + PostGIS   │
        └──────────────────────────────────────┘

        OFFLINE, not in the request path:
        ────────────────────────────────────────
        │  insar/pipeline/  ISCE2 → MintPy     │
        │  run ahead of demo, output loaded    │
        │  into deformation_points/series      │
        ────────────────────────────────────────
```

The dashed boundary matters. **InSAR processing is not a service.** It is an offline batch that produces a dataset. The API reads that dataset.

---

## 2. Region config

One constant, imported everywhere. Never hardcode coordinates twice.

```python
# services/api/config.py
REGION = {
    "name": "Aizawl district, Mizoram",
    "bbox": {"west": 92.55, "south": 23.55, "east": 93.05, "north": 24.05},
    "grid_m": 100,          # finer than the 250 m flood grid — hill terrain
    "crs": "EPSG:4326",
    "utm": "EPSG:32646",    # for metric operations
    "hq": (23.7271, 92.7176),   # Aizawl — isolation scoring anchor
}
LANGUAGES = ["en", "hi", "as"]   # English, Hindi, Assamese
INSAR_CORRIDOR = {
    "id": "aizawl-ridge-01",
    "description": "Set to the corridor actually processed. Do not guess.",
}
```

This did not exist as a single constant before this pivot — `services/api/ingest/config.py` and `services/api/risk/features.py` each hardcoded their own, disagreeing, Srikakulam-specific bbox. Both are refactored to import from here.

**Grid resolution is 100 m, not 250 m.** Landslide failure surfaces are tens of metres across; a 250 m cell averages a failing slope into its stable neighbours and the signal disappears. This is a real change from the flood build, not a parameter tweak.

---

## 3. Terrain (`services/api/terrain/`)

Carries from the previous build, extended. Runs once at seed.

| Feature | Source | Note |
|---|---|---|
| `elevation_m` | Copernicus DEM GLO-30 | base |
| `slope_deg` | derived | dominant, but watch for it dominating too much |
| `aspect_deg` | derived | encode as sin/cos, **never as raw degrees** — 359° and 1° are adjacent |
| `curv_plan`, `curv_prof` | derived | concave hollows concentrate subsurface flow |
| `ls_factor` | derived | slope length × steepness |
| `hand_m` | pysheds | carries; matters for the flash-flood secondary hazard |
| `twi` | derived | carries |
| `dist_stream_m` | OSM waterways | carries |
| `dist_road_m` | OSM roads | **new and important** |
| `is_cut_slope` | derived | `dist_road_m < 50` AND `slope_deg > 25` |
| `lithology` | GSI | categorical |
| `landcover` | ESA WorldCover | categorical |

**`is_cut_slope` is worth calling out.** The problem statement names "unplanned hill cutting" as a cause. This feature encodes it directly, and it will show up in the feature importances — which is a strong demo moment, because it connects a model output to a sentence in the brief.

**Aspect encoding trap:** aspect is circular. Feed `sin(aspect)` and `cos(aspect)` as two features. Feeding degrees directly teaches the model that north-facing and north-north-east-facing slopes are maximally different.

---

## 4. Risk model (`services/api/risk/`)

LightGBM binary classifier. Same code as the flood build; new features, new target.

### Labels

Presence-only inventory: GSI landslide records plus the NASA Global Landslide Catalog, buffered to the 100 m grid.

**Negative sampling is the whole problem here.** Landslide inventories record where landslides happened, never where they did not.

- Do **not** sample negatives uniformly across the district. That produces a model that has learned "steep = landslide" and nothing more.
- Sample negatives from cells that are plausibly susceptible — slope above 15°, within the same lithology classes — but have no recorded event within a buffer.
- Ratio 1:3 positive to negative.
- **Report feature importances and inspect them.** If slope alone carries more than ~40% of the model, the negative sampling is wrong. Fix the sampling, not the model.

### Rainfall as a trigger

Static susceptibility and dynamic triggering are different things. Model both:

```
susceptibility = f(terrain, geology, landcover, road_cut)     # static
trigger        = g(rain_1d, rain_3d, rain_7d, rain_15d,       # dynamic
                   rain_intensity_max, soil_moisture)
risk           = susceptibility × normalise(trigger)
```

The 15-day antecedent window matters: slope failure typically follows sustained saturation and then an intensity spike, not a single storm. A model with only a 24-hour window will miss the mechanism.

### Output

`risk_score` in [0,1], banded to the IMD warning ladder (0 normal → 4 severe), with per-cell top-3 feature attribution and a `provenance` flag (`model` or `index`) exposed through the API and rendered in the UI.

---

## 5. InSAR (`services/api/insar/`)

### Offline pipeline — `insar/pipeline/`, not invoked at runtime

```
1. Acquire Sentinel-1 SLC pairs over the corridor (ASF Vertex, free account)
   → single track, single orbit direction, >=20 acquisitions
2. Co-register and generate interferograms (ISCE2 topsApp)
3. SBAS time-series inversion (MintPy smallbaselineApp)
4. Export per-point: LOS velocity (mm/yr), coherence, displacement series
5. Load into deformation_points / deformation_series
```

**Discard points with coherence < 0.3.** Vegetated hill slopes decorrelate badly, and low-coherence points produce confident-looking nonsense. This is the single most likely way to embarrass yourself in front of a geologist.

### Runtime service

Reads the loaded dataset only. Computes and serves:

```python
velocity_mm_yr    # LOS, negative = moving away from sensor (subsiding)
acceleration      # second derivative of the displacement series
alert_state       # stable | creeping | accelerating
```

**Acceleration is the early-warning signal, not velocity.** Many hill slopes creep steadily for years without failing. Onset of acceleration is what precedes failure. Classify:

```
|v| < 5 mm/yr                        -> stable
|v| >= 5 mm/yr, acceleration ~ 0      -> creeping
acceleration > threshold, sustained  -> accelerating   # this is the alert
```

Make this distinction explicit in the UI. It is the difference between a system that flags every steep slope and one that flags the slope that is about to go.

### Honesty constraints

- Points render only where they were measured. No interpolation across unprocessed area.
- The corridor boundary is drawn on the map. Outside it, the deformation layer is empty, and the UI says so.
- Every point carries its acquisition count and date range.

---

## 6. Roads and isolation (`services/api/roads/`)

**New work, not carried** — see `docs/MIGRATION.md` §2. The Srikakulam build never had an OSM road graph; `roads/routing.py` there only draws dispatch routes via a public routing API.

```python
def isolation_scores() -> dict[int, float]:
    """
    Remove blocked edges from the road graph.
    Find connected components.
    For each settlement, score by:
      - size of its component (smaller = more isolated)
      - whether it retains a path to the district HQ
      - population within the component
    """
```

A settlement with no remaining path to the district headquarters scores 1.0. This term enters triage directly.

**Why it matters, and why it is the strongest thing in this build after InSAR:** in a flood, people can often self-evacuate. In a hill landslide, a blocked ridge road removes every route out. Isolation is not a proxy for hazard exposure — it is an independent axis of urgency, and it is specific to this hazard's mechanism. Most teams will not have it.

Road blocking has three sources: predicted (from risk), reported (citizen or field official), and confirmed (admin). Store the source; display it.

**The demo road-block trigger is built and tested here**, as soon as isolation scoring exists — not bolted onto `seed/demo.py` right before rehearsal. A deterministic button blocks one named ridge segment and isolates 2-3 known settlements. It is the peak of the demo (`docs/WORKFLOW.md` §7) and needs to be verified days before rehearsal, not during it.

---

## 7. Citizen reports (`services/api/reports/`)

```
POST /reports                 # single, upsert on client uuid
POST /reports/sync            # bulk offline flush, idempotent
GET  /reports?status=&bbox=
PATCH /reports/{id}           # verify / dismiss / mark duplicate
```

**Built before the citizen app's capture flow** (`docs/MIGRATION.md` §6.3) — the app is written against a real endpoint, not a mock.

### Pipeline

1. **Client-side:** capture photo, read EXIF GPS (fall back to device geolocation), run on-device ONNX classifier, queue in IndexedDB with a client-generated UUID.
2. **Upload:** media to Supabase Storage, metadata to Postgres, upsert on the client UUID so replay is harmless.
3. **Deduplicate:** cluster reports within 100 m and 60 minutes into a `cluster_id`. Ten photos of one landslide are one incident, and an unclustered queue is unusable.
4. **Triage:** admin queue ordered by cluster size × auto-classifier confidence × area risk.

### On-device classifier

MobileNetV3 fine-tuned on four classes: `crack`, `slope_movement`, `road_blocked`, `no_hazard`. Exported to ONNX, run with `onnxruntime-web`.

**It does not need to be accurate.** It needs to pre-sort the queue and work offline. Present it as triage assistance, never as detection. If accuracy is poor, say so and keep it — the honest framing is stronger than a suppressed feature.

**Privacy:** store a hashed device identifier, never identity. Strip EXIF beyond coordinates. Say this unprompted; a ministry panel will care.

---

## 8. Alerts (`services/api/alerts/`)

CAP (Common Alerting Protocol) XML generation. CAP is the international standard Indian agencies already use, so this interoperates with existing infrastructure rather than competing with it.

```python
def generate_cap(severity, geofence, languages, headline, instruction) -> str
def evaluate_geofences(location) -> list[Alert]   # citizen client polls or subscribes
```

**Languages at demo scope: English, Hindi, Assamese.** Structure supports more; only these three are translated. No other language — Mizo included — is generated without a native speaker available to verify emergency instructions. Templates in `alerts/templates/{lang}.json`, not concatenated strings.

**Delivery is out of scope.** The payload is generated and displayed. Say so.

---

## 9. Dispatch (`services/api/dispatch/`)

Carries. Severity re-weighted:

```
sigma = 0.28*persons + 0.28*category + 0.22*area_risk + 0.12*wait + 0.10*isolation
```

All five components persisted individually.

The `qubo-dispatch` package is unchanged. Default backend is `ortools`. QAOA remains available behind the router.

**UI treatment:** one line in the dispatch panel — `solver: ortools · formulation: QUBO · quantum-ready`. No heading, no badge, no nav item. If asked, the answer is in `CLAUDE.md` §2.3.

---

## 10. Clients

### `packages/ui/`
Extract early, before the clients can diverge. Design tokens, map primitives, severity chips, form controls, i18n provider.

### `apps/admin/`
Renamed from `apps/web` in the Srikakulam build; evolves from there. New: deformation panel with per-point time series chart, report triage queue with media preview, road status and isolation view. Carried: risk map, request queue, dispatch, append-only ledger.

### `apps/citizen/`
Vite PWA, Capacitor-wrapped for Android.

- `@capacitor/geolocation` — location with explicit consent, foreground only
- `@capacitor/camera` — capture
- Offline queue: same IndexedDB pattern as the admin client, same idempotency contract
- Geo-fenced alerts, evaluated client-side against cached fences so they work offline
- `react-i18next`, three locales (English, Hindi, Assamese)

**Location consent:** explicit opt-in, foreground only, revocable, with a plain-language explanation of use. Do not track in the background. A ministry panel will ask.

### Capacitor build

```bash
npm run build
npx cap add android
npx cap sync
npx cap open android      # then build the .apk in Android Studio
```

Roughly two hours including SDK setup. **If it fights you past that, ship the PWA and move on** — the PWA is the deliverable, the `.apk` is a bonus.

---

## 11. Testing floor

Two release gates carry from the previous build:

- `test_constraints.py` — no dispatch result double-books a unit or a request, on any backend, across 500 random instances
- `test_fallback.py` — with Qiskit patched to fail on import, a valid assignment is still returned

New:

- `test_sync.py` — replayed offline batches produce no duplicate rows
- `test_isolation.py` — blocking a known cut edge marks exactly the expected settlements isolated

---

## 12. Environment

```
# additions to the carried requirements.txt
python-multipart==0.0.20
Pillow==11.1.0
exifread==3.0.0
# InSAR pipeline only, NOT installed on the API host:
#   isce2, mintpy — install in a separate conda env
```

```
# apps/citizen additions
@capacitor/core @capacitor/android @capacitor/geolocation @capacitor/camera
react-i18next i18next onnxruntime-web
```

**Keep ISCE2 and MintPy out of the API environment.** They are heavy, fragile, and only needed offline. Putting them in `requirements.txt` will break your deploy.
