# Q-resQ NER pivot — overview + sub-project 1 (Foundation) design

**Status:** approved by user 2026-09-05, ready for implementation planning.
**Scope of this document:** the whole pivot's decomposition (roadmap only,
sub-projects 2-12 are not designed yet — each gets its own brainstorm/spec
cycle when we reach it), plus a fully detailed design for sub-project 1
(Foundation), which is approved for immediate implementation.

---

## 1. Why

Q-resQ (PRAHARI) is a 24-hour hackathon flood-dispatch platform for
Srikakulam district, Andhra Pradesh — risk map + QUBO-based rescue dispatch.
It is being pivoted into **Q-resQ NER**: an AI landslide early-warning and
risk-monitoring platform for Aizawl district, Mizoram, for Smart India
Hackathon 2026, Problem Statement 26001 (Ministry of DoNER). Full framing,
scope calls, and technical detail live in the docs listed in §4 — this
document is the execution roadmap on top of them, not a replacement.

Team: 3 people, 6-day build window, starting 2026-09-05. In practice one
executor (this agent) drives most of the implementation sequentially rather
than three humans working in parallel — independent pieces are still done
in whatever order unblocks fastest, but there is no assumption of three
simultaneous workstreams.

---

## 2. Standing rules for the whole build

These apply to every sub-project, not just Foundation:

- **Stop and ask before:** adding a dependency not already listed in the
  stack docs, inventing a colour outside `docs/DESIGN.md`'s tokens, or
  claiming a performance/accuracy result.
- **If a data source is unreachable, say so.** Never substitute a different
  source, region, or date range without telling the user first.
- **Language scope is English, Hindi, Assamese only.** i18n is structured to
  support more languages, but Mizo (or any other regional language) is never
  generated — there is no native speaker available to verify emergency
  instructions, and unverified translations of emergency messaging do not
  ship. Every doc reference to "four languages" or `lus`/Mizo is corrected
  to three languages, English/Hindi/Assamese, throughout.
- **Handled outside this build, do not block on any of them** — build
  against fixtures and state what shape the real data needs to arrive in:
  - Sentinel-1 SLC download (Earthdata/ASF Vertex)
  - Supabase project + deploy accounts (Railway/Vercel or equivalent)
  - GSI Bhukosh landslide inventory + lithology export
  - Photo classifier training dataset curation
  - Android Studio / Capacitor toolchain setup
- **If something genuinely needs a human** (an account, a credential, a
  judgment call only the user can make, physical hardware), say so early
  rather than working around it or guessing.

---

## 3. Corrections to the drafted docs, found by reading the actual repo

The documents drafted in an earlier planning pass describe some things as
already true that are not, because they were written against the target
end-state rather than the current codebase. These get corrected when the
docs are written to disk (§5.1), not silently carried forward:

- **The road graph does not carry over.** `MIGRATION.md §2` and
  `README.md` describe "OSM ingest, passability, Dijkstra over the residual
  graph" as already carried. It doesn't exist. `services/api/roads/`
  currently contains one file, `routing.py` (committed 2026-09-05), which
  calls the public OSRM demo server to draw a route line for the dispatch
  UI — no graph, no passability model, no Dijkstra, no isolation. This is
  new work (sub-project 2 ingest + sub-project 5a), not carried code.
- **The single `REGION` constant does not exist yet.** `TRD.md §2`
  describes one constant every module imports. In reality there are two
  disconnected region definitions today:
  - `services/api/ingest/config.py` — `BBOX` for Srikakulam
    `(83.30, 18.00, 84.55, 19.25)`, plus Titli-specific date constants.
  - `services/api/risk/features.py` — its own, smaller, independently
    hardcoded `DEMO_BBOX = (83.75, 18.20, 84.05, 18.45)`, plus hardcoded
    Srikakulam DEM/rainfall file paths and `EPSG:32644` (Srikakulam's UTM
    zone) in `risk/terrain.py`.

  These two already disagree with each other. "Swap the region constant" is
  therefore "create the shared constant for the first time, then point both
  modules at it," not a one-line edit.

---

## 4. Documents to write to disk (sub-project 1, step 1)

None of the following exist in this repo yet except where noted. All get
written with the corrections from §2 (language scope) and §3 (road graph,
region constant) baked in — not written verbatim from the earlier drafts
and then patched.

| File | Action |
|---|---|
| `CLAUDE.md` (root) | Overwrite — Q-resQ NER build rules |
| `README.md` | Overwrite — corrected per §3, 3 languages |
| `docs/MIGRATION.md` | New — corrected per §3 |
| `docs/PRD.md` | Overwrite — 3 languages |
| `docs/TRD.md` | Overwrite — §2 region constant reflects reality once created, §8 3 languages |
| `docs/WORKFLOW.md` | Overwrite — reflects the 5a/5b split and reports-before-citizen-app order from the approved decomposition (§7 below) |
| `docs/DATA.md` | New |
| `docs/TRAINING.md` | New |
| `docs/DESIGN.md` | No change — already carries unchanged, tokens already match |
| `services/api/BUILD_SPEC.md` | Overwrite — roads/isolation section gains the demo road-block trigger requirement (moved from seed/demo.py, see §7) |
| `apps/BUILD_SPEC.md` | New — 3 languages, `apps/admin` naming |
| `services/api/schema.sql` | Overwrite — additive schema from the draft; **not applied to any database**, see §6 step 5 |

---

## 5. Sub-project 1 — Foundation (fully designed, approved for implementation)

### 5.1 Region config

Create `services/api/config.py`:

```python
REGION = {
    "name": "Aizawl district, Mizoram",
    "bbox": {"west": 92.55, "south": 23.55, "east": 93.05, "north": 24.05},
    "grid_m": 100,
    "crs": "EPSG:4326",
    "utm": "EPSG:32646",
    "hq": (23.7271, 92.7176),
}
LANGUAGES = ["en", "hi", "as"]
```

Refactor `services/api/ingest/config.py` to import `BBOX` from here (or
re-export it) instead of defining its own. Refactor `services/api/risk/
features.py` to import the same bbox/grid/UTM instead of its own
`DEMO_BBOX`/hardcoded paths/`EPSG:32644`. Rename Srikakulam-specific file
paths (`srikakulam_dem.tif`, `srikakulam_dem_demo_crop.tif`,
`RF25_ind2018_rfp25.nc`) to Aizawl-appropriate names.

### 5.2 Delete dead Srikakulam-only code

Per `MIGRATION.md §5`, reconciled against what's actually in the repo:

- `services/api/ingest/cyclone.py` — IBTrACS cyclone-track ingest, flood-only
- `services/api/ingest/sar.py` — if flood-specific SAR thresholding, confirm
  contents before deleting (verify at implementation time; keep if it turns
  out to be generic SAR ingest reusable for InSAR prep, delete if
  Srikakulam/flood-specific)
- `routers/seed.py` — the `seed_titli` endpoint and its unit/request
  fixtures, and the Titli-specific `_CATEGORY_WEIGHTS_BY_TYPE` dict
- `services/api/ingest/config.py` — `TITLI_LANDFALL_DATE`,
  `DEFAULT_EVENT_START`, `DEFAULT_EVENT_END`
- **Approved for deletion (2026-09-05):** the multi-hazard disaster-type
  switch shipped in commit `bbbc4be` — `risk/heuristic.py`'s
  `DISASTER_WEIGHTS` dict and the `disaster_type` parameter threading
  through `risk/features.py` / `routers/risk.py` / `routers/seed.py`; the
  `/risk/live` and `/risk/live/range` endpoints; `LiveRiskPanel.tsx`. This is
  Srikakulam-flood-demo-specific — NER is one dominant hazard (landslide)
  with a secondary flash-flood hazard, not four peer hazard types behind a
  switch. Deleting now rather than leaving it for sub-project 3 to
  encounter mid-rewrite.
- Cached Srikakulam data files under `services/api/data/raw/` (DEM tifs,
  `.npy` risk caches, rainfall parquets, `titli_track.csv`) — these are
  gitignored working files, not tracked; delete locally as part of the
  cache invalidation, no commit needed.

Commit this deletion separately from anything added, per `MIGRATION.md
§8`'s own instruction, so it's independently reviewable.

### 5.3 Rename `apps/web` → `apps/admin`

**Approved (2026-09-05).** One rename now, before `packages/ui` extraction
and a second client (`apps/citizen`) make it more disruptive later. Update:
- `apps/web/Dockerfile` → `apps/admin/Dockerfile`, and any path inside it
- `docs/DEPLOYMENT.md` references to `apps/web`
- Any Vite/build config referencing the `apps/web` path

This touches only repository paths. No live deploy account, DNS, or
environment variable is touched by this step — that remains "handled
separately" per §2.

### 5.4 Prepare, don't apply, the schema

Write `services/api/schema.sql` (additive, includes all carried tables plus
the new NER tables — deformation, citizen reports, settlements, alerts,
sensor readings, road segment blockage columns). Do **not** run
`apply_schema.py` or `psql $DATABASE_URL -f services/api/schema.sql` against
any database in this step — Supabase project setup is handled separately
per §2. State plainly in the handoff what command applies it once a
database exists.

### 5.5 Prove the pipeline for real

Run `services/api/ingest/dem.py` against the new Aizawl bbox from §5.1 —
Copernicus DEM GLO-30 via Planetary Computer STAC, no API key required, not
blocked by anything in the "handled separately" list. Then run
`risk/terrain.py`'s `compute_hand` / `compute_slope` / `compute_twi` /
`compute_stream_distance` against the real fetched DEM and print shape,
resolution, and elevation min/max. This is the actual confidence check —
the terrain pipeline either produces real numbers for Aizawl or it doesn't;
nothing is simulated or asserted without running it.

### 5.6 Verification for Foundation

- `services/api/tests/` suite still passes after the deletions in §5.2
  (adjust/remove tests that only exercised deleted Titli/multi-hazard code)
- `GET /health` still returns `{"status": "ok"}`
- The DEM fetch in §5.5 completes and prints real shape/elevation numbers
  for the Aizawl bbox
- No remaining reference to `EPSG:32644`, `srikakulam`, `Titli`, or the
  Srikakulam bbox anywhere under `services/api/` (grep-clean)
- `apps/admin` builds and runs (`npm run dev`) after the rename

---

## 6. Roadmap — sub-projects 2-12 (not designed yet)

Listed for sequencing only. Each gets its own brainstorm → design → plan
cycle when we reach it, per the approved decomposition:

| # | Sub-project | Depends on |
|---|---|---|
| 2 | Data ingest — DEM, terrain derivatives, OSM (roads/settlements/facilities), road-cut, landslide labels, rainfall, soil moisture, landcover | 1 |
| 3 | Risk model retrain — features, negative sampling, spatial-CV LightGBM, trigger index, fallback heuristic | 2 |
| 4 | `packages/ui` extraction + admin console evolution | 1 |
| 5a | Roads + isolation scoring (backend) — graph, connected components, settlement scoring, block/clear endpoint, **demo road-block trigger built and tested here, not in §12** | 2 |
| 5b | Roads + isolation UI | 4, 5a |
| 6 | Reports backend — `POST /reports`, `POST /reports/sync`, upsert on client UUID, clustering | 1 |
| 7 | Citizen app — capture flow, offline queue, on-device ONNX classifier, i18n (en/hi/as), geofenced alerts | 4, 6 |
| 8 | Alerts (CAP generation) | 5a, 6 |
| 9 | Dispatch rewire — isolation term in severity | 5a |
| 10 | InSAR — offline pipeline + loader + runtime service, one corridor, hard cutoff | independent; SLC download starts day 1 externally |
| 11 | Capacitor Android wrap | 7 |
| 12 | Demo seed, design pass, rehearsal | everything |

---

## 7. Self-review notes

- No placeholders or TBDs remain in the Foundation design (§5); the
  ingest/sar.py deletion decision is explicitly deferred to implementation
  time with a clear criterion (flood-specific vs generic), not left vague.
- Internally consistent: the language-scope correction (§2) is reflected in
  every doc listed in §4, not just TRD.md.
- Scope check: this document covers one fully-designed sub-project
  (Foundation) plus a roadmap. It is sized for one implementation plan.
- Ambiguity check: "delete `ingest/sar.py`" was the one genuinely ambiguous
  item pending a content check — resolved above by stating the decision
  criterion rather than guessing.
