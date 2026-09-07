# MIGRATION — Q-ResQ (Srikakulam floods) → Q-ResQ NER (Aizawl landslides)

Read this before touching code. This is a pivot, not a rewrite.

---

## 1. What changed at the top

| | Before | Now |
|---|---|---|
| Event | Cyclone Titli, Oct 2018 | Landslide season, Aizawl |
| Geography | Srikakulam — coastal alluvial plain | Aizawl — steep hill terrain |
| Primary hazard | Riverine and urban flood | Landslide and slope failure |
| Headline technique | QUBO dispatch | **InSAR deformation monitoring** |
| Clients | One admin console | **Two: admin + citizen** |
| Judge | Hackathon panel | **Ministry (MDoNER) + industry** |

The last row drives more decisions than any other. The previous audience rewarded novelty; this one rewards deployability, honesty about data provenance, and evidence you read the brief.

**One narrative worth keeping:** in the Srikakulam build the landslide-type risk weighting correctly mattered least of all hazard types, because a coastal plain has no landslide hazard. On Aizawl terrain, landslide risk now carries the entire product. That is calibration demonstrated across two geographies, and it is worth one sentence in the pitch.

---

## 2. Carries unchanged — do not rewrite

- **`packages/qubo-dispatch/`** — the whole optimization package. Formulation, penalties, partitioner, solver router, tests. Zero changes.
- **`docs/DESIGN.md`** — design tokens, IMD warning ladder, ban list. The visual language is unchanged.
- **FastAPI skeleton, Pydantic models, Supabase client, deploy config.**

**Corrected from an earlier draft of this document:** the offline layer (Workbox, PMTiles, IndexedDB queue, idempotent client-UUID sync) and the road graph were both described here as carrying over unchanged. Checked against the actual repository on 2026-09-06: the offline layer was never built in the Srikakulam codebase either — there is no service worker, no PMTiles caching, no IndexedDB queue there. And `services/api/roads/` contains one file, a thin wrapper around the public OSRM routing API for drawing dispatch routes — no OSM graph ingest, no passability model, no Dijkstra, no isolation scoring. **Both are new work for this pivot**, not carried code. Offline capability and isolation scoring are both named requirements of this problem statement, so they get built properly here — they just are not a reuse of anything that already exists.

---

## 3. Carries with extension

### `services/api/terrain/`
The DEM pipeline runs on new coordinates with minimal code change (region constant swap — see `docs/TRD.md` §2). But flat-terrain features are insufficient for landslides. Add:

| New feature | Why |
|---|---|
| **Aspect** | Slope orientation. Controls insolation, moisture retention, and failure direction. |
| **Plan and profile curvature** | Concave hollows concentrate subsurface flow. Strong landslide predictor. |
| **Slope length (LS factor)** | Longer slopes accumulate more driving force. |
| **Lithology / geology** | From GSI. NER is structurally weak sedimentary rock in much of Mizoram. |
| **Distance to road / road cut** | The problem statement names "unplanned hill cutting" explicitly. Cut slopes are a dominant anthropogenic trigger. Compute distance to OSM road centreline and flag cut faces. |

HAND, slope, TWI, and distance to stream all carry — they still matter, they just matter less than they did for flooding.

### `services/api/dispatch/`
Carries. Severity weights are re-tuned for landslides:

```
old (flood):      0.30 people + 0.30 category + 0.25 area_risk + 0.15 wait
new (landslide):  0.28 people + 0.28 category + 0.22 area_risk
                + 0.12 wait   + 0.10 isolation_score
```

`isolation_score` is new and is a landslide-specific term: settlements cut off by a road blockage have no self-evacuation route, so their effective urgency rises independently of their own hazard exposure. Computed from the road graph as connected-component size after removing blocked edges. **This is the single most defensible addition to the triage model, because it is a direct consequence of the hazard's mechanism.**

### `apps/admin/`
The existing console (`apps/web` in the Srikakulam build, renamed) evolves. New panels: deformation time series, citizen report triage queue, road connectivity status. Existing panels (risk map, request queue, dispatch, ledger) carry.

---

## 4. Retrained — same code, new target

### `services/api/risk/`
LightGBM stays. The feature matrix and target change completely.

- **Target:** landslide occurrence, from the GSI landslide inventory and the NASA Global Landslide Catalog. Point events buffered to the analysis grid.
- **This is a better data position than the flood build.** There the labels came from thresholding SAR and were noisy. Here there is a curated, partly field-validated inventory. Say so.
- **Negative sampling matters.** Landslide inventories are presence-only. Sample absences from terrain that is plausibly at risk but has no recorded event — do not sample uniformly, or the model learns "steep = landslide" and nothing else.
- **Rainfall becomes a trigger, not a static feature.** Antecedent rainfall over 1, 3, 7 and 15 days plus rainfall intensity. Landslides respond to accumulated saturation followed by an intensity spike, and the 15-day window is what captures that.

---

## 5. Dead — remove

- Titli scenario seed and all its fixtures
- The multi-hazard disaster-type switch (cyclone / flood / urban_flooding / landslide re-weighting of one physical index, and the associated `/risk/live` endpoints and UI panel) — NER is one dominant hazard with secondary flash flooding, not four peer hazard types behind a switch
- Cyclone track ingest (IBTrACS)
- Srikakulam bounding box, cached data files, and Srikakulam-specific OSM extract

Delete these rather than leaving them dormant. Dead code in a six-day build is a trap.

---

## 6. New — the actual work

Ordered by build risk, highest first.

### 6.1 InSAR deformation (`services/api/insar/`) — HIGHEST RISK
Sentinel-1 SLC pairs → interferograms → SBAS time series → per-point line-of-sight displacement in mm/yr.

**Processed offline. Pre-computed. One corridor.** See `CLAUDE.md` §2.1. The API serves a static dataset; the processing scripts live in the repo and are documented but are not invoked at request time.

### 6.2 Citizen client (`apps/citizen/`)
PWA, Capacitor-wrapped for Android. Geotagged photo and video upload, geo-fenced alerts, offline queue, multilingual (English, Hindi, Assamese), help request.

### 6.3 Report triage (`services/api/reports/`)
Citizen submissions with EXIF geolocation, on-device pre-classification, deduplication by spatial-temporal clustering, admin review queue. **Built before the citizen app's capture flow** — the app is built against a real endpoint, not a mock.

### 6.4 Roads and isolation (`services/api/roads/`)
OSM road graph ingest, blockage tracking, connected-component isolation scoring for settlements. Genuinely new — see the correction in §2. Backend (graph, scoring, block/clear endpoint, the deterministic demo road-block trigger) is built as soon as roads are ingested; the UI depends on `packages/ui`.

### 6.5 Alerts (`services/api/alerts/`)
CAP-format payload generation, geo-fence evaluation, multilingual message templates (English, Hindi, Assamese). **Delivery to an SMS gateway is out of scope** — the payload is generated and displayed. Say that plainly; it is a procurement problem, not an engineering one.

### 6.6 Offline layer
Workbox service worker, PMTiles tile caching, IndexedDB queue with idempotent client-UUID sync. New, not carried (see §2's correction) — but the pattern is well understood and low-risk to build.

### 6.7 Shared UI package (`packages/ui/`)
Extracted from the existing admin components so both clients share tokens, map primitives, and form controls.

---

## 7. Schema changes

Additive only. Nothing existing is dropped. Full DDL is `services/api/schema.sql` — that file is the source of truth; do not retype it from this document.

---

## 8. Migration order

Follow this. Each step leaves the repo in a working state.

1. Branch from the existing repo. Do not fork — history is useful.
2. Introduce the single region constant (`services/api/config.py`) and swap it to Aizawl. Verify the terrain pipeline runs unchanged on the new bbox against a real fetched DEM. **Verify this before anything else** — it is the cheapest possible confidence check.
3. Delete everything in §5. Commit the deletion separately so it is reviewable.
4. Apply the additive schema in `services/api/schema.sql` (once a database exists — not before).
5. Extend terrain features per §3.
6. Retrain risk on landslide labels per §4.
7. Ingest the OSM road network and build isolation scoring (§6.4).
8. Build reports intake (§6.3), then the citizen client against it (§6.2).
9. Extract `packages/ui/` (§6.7), evolve `apps/admin/`.
10. Alerts (§6.5), dispatch rewire with the isolation term.
11. InSAR last, timeboxed (§6.1). If it is not producing a usable time series by the cutoff in `docs/WORKFLOW.md`, ship the pre-computed corridor and move on.
