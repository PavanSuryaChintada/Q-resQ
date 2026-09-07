# NER Pivot Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repository's code match the Q-resQ NER pivot at the config/region level — one real region constant, dead Srikakulam-only code removed, `apps/web` renamed to `apps/admin`, and the terrain pipeline proven to run against a real Aizawl DEM.

**Architecture:** No new services. This is a targeted refactor: introduce `services/api/config.py` as the single source of truth for region/language constants, point the two currently-disagreeing region definitions at it, delete code that has no role in a single-hazard NER build, rename one directory, and run one real data fetch as a verification step.

**Tech Stack:** Python 3.11 / FastAPI (backend), TypeScript / React / Vite (frontend) — no new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-05-ner-pivot-foundation-design.md`

## Global Constraints

- Stop and ask before adding a dependency, inventing a colour, or claiming a performance result.
- If a data source is unreachable, say so — never substitute a different source, region, or date range.
- Languages are English, Hindi, Assamese only — no other language is generated.
- Commit the dead-code deletion (Task 2) separately from the region-config addition (Task 1), per `docs/MIGRATION.md` §8.
- Do not apply `services/api/schema.sql` to any database — Supabase setup is out of scope for this plan.

---

### Task 1: Single region config

**Files:**
- Create: `services/api/config.py`
- Modify: `services/api/ingest/config.py`
- Modify: `services/api/risk/features.py`
- Modify: `services/api/risk/terrain.py:18` (`_SRIKAKULAM_UTM_CRS`)
- Test: `services/api/tests/test_config.py`

**Interfaces:**
- Produces: `services.api.config.REGION: dict` with keys `name, bbox (dict: west/south/east/north), grid_m, crs, utm, hq (tuple[float,float])`; `services.api.config.LANGUAGES: list[str]`.
- Consumes (by `ingest/config.py`): `REGION["bbox"]` to build its own `BBOX` tuple `(west, south, east, north)`.
- Consumes (by `risk/features.py`): `REGION["bbox"]` for `DEMO_BBOX`, `REGION["utm"]` in place of the old hardcoded CRS.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_config.py
from config import REGION, LANGUAGES


def test_region_is_aizawl():
    assert REGION["name"] == "Aizawl district, Mizoram"
    assert REGION["bbox"] == {"west": 92.55, "south": 23.55, "east": 93.05, "north": 24.05}
    assert REGION["grid_m"] == 100
    assert REGION["utm"] == "EPSG:32646"
    assert REGION["hq"] == (23.7271, 92.7176)


def test_languages_are_three_only():
    assert LANGUAGES == ["en", "hi", "as"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Create `services/api/config.py`**

```python
"""Single source of truth for region and language constants. Every
module that needs the district bbox, grid resolution, or supported
languages imports from here — never redefines them.
"""

from __future__ import annotations

REGION = {
    "name": "Aizawl district, Mizoram",
    "bbox": {"west": 92.55, "south": 23.55, "east": 93.05, "north": 24.05},
    "grid_m": 100,
    "crs": "EPSG:4326",
    "utm": "EPSG:32646",
    "hq": (23.7271, 92.7176),  # Aizawl — isolation scoring anchor
}

LANGUAGES = ["en", "hi", "as"]  # English, Hindi, Assamese — no others generated

INSAR_CORRIDOR = {
    "id": "aizawl-ridge-01",
    "description": "Set to the corridor actually processed. Do not guess.",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/api && python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Refactor `services/api/ingest/config.py` to derive `BBOX` from `config.REGION`**

Replace the hardcoded Srikakulam `BBOX` and remove the Titli-specific constants (`TITLI_LANDFALL_DATE`, `DEFAULT_EVENT_START`, `DEFAULT_EVENT_END` — dead per Task 2, but remove them here since this file is being edited anyway and they have no NER equivalent):

```python
"""Shared config for the ingest layer. Import BBOX from here - never
hardcode it in an individual script.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

INGEST_DIR = Path(__file__).resolve().parent
API_DIR = INGEST_DIR.parent
sys.path.insert(0, str(API_DIR)) if str(API_DIR) not in sys.path else None

from config import REGION  # noqa: E402

# (west, south, east, north) in EPSG:4326 degrees — Aizawl district, Mizoram
_bbox = REGION["bbox"]
BBOX = (_bbox["west"], _bbox["south"], _bbox["east"], _bbox["north"])

DATA_RAW_DIR = API_DIR / "data" / "raw"
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

PLANETARY_COMPUTER_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)
```

Note: `services/api` is already the working directory / on `sys.path` when the API runs (`main.py` imports `from routers import ...` the same way), so `from config import REGION` resolves the same way sibling imports already do elsewhere in this codebase — the `sys.path.insert` line above is defensive for the case `ingest/` scripts are run standalone (`python ingest/dem.py` from inside `services/api/`). Verify this actually works in Step 7 rather than assuming it.

- [ ] **Step 6: Refactor `services/api/risk/features.py` to use the shared region and rename Srikakulam-specific paths**

Replace lines 24-51 (`FULL_DEM_PATH` through `EVENT_END_DATE`):

```python
from config import REGION

_API_DIR = Path(__file__).resolve().parents[1]
FULL_DEM_PATH = str(_API_DIR / "data" / "raw" / "dem_aizawl.tif")
DEM_PATH = str(_API_DIR / "data" / "raw" / "dem_aizawl_demo_crop.tif")
RAINFALL_NC_PATH = os.environ.get(
    "RF25_RAINFALL_NC_PATH", str(_API_DIR / "data" / "raw" / "rainfall_aizawl.nc")
)
CACHE_DIR = _API_DIR / "data" / "raw"

_TERRAIN_CACHE_PATH = CACHE_DIR / "risk_terrain_cache.npy"
_TERRAIN_COLS = ["lat", "lon", "hand_m", "slope_deg", "twi", "dist_stream_m", "rain_72h_mm"]

_bbox = REGION["bbox"]
DEMO_BBOX = (_bbox["west"], _bbox["south"], _bbox["east"], _bbox["north"])
GRID_CELL_M = float(REGION["grid_m"])
```

This removes `EVENT_END_DATE` (Titli-specific, no longer used once the multi-hazard/live-risk code from Task 2 is gone) and the per-`disaster_type` cache path / `DISASTER_WEIGHTS` import — both handled fully in Task 2. For this step, leave `build_risk_cells`'s signature and body as-is except for the constants it references; Task 2 removes the `disaster_type` parameter itself.

Also update the module docstring's `DEMO_BBOX` comment to describe Aizawl instead of Srikakulam.

- [ ] **Step 7: Update the UTM zone in `services/api/risk/terrain.py`**

```python
# services/api/risk/terrain.py:18
_AIZAWL_UTM_CRS = "EPSG:32646"  # UTM zone 46N - covers Aizawl district, Mizoram
```

Rename every use of `_SRIKAKULAM_UTM_CRS` in this file to `_AIZAWL_UTM_CRS`.

- [ ] **Step 8: Verify the refactor doesn't break imports**

Run: `cd services/api && python -c "import risk.features; import ingest.config; print('ok')"`
Expected: prints `ok` with no traceback. If `ingest.config`'s `from config import REGION` fails, fix the import path before continuing — do not proceed to Task 2 with a broken import.

- [ ] **Step 9: Commit**

```bash
git add services/api/config.py services/api/tests/test_config.py services/api/ingest/config.py services/api/risk/features.py services/api/risk/terrain.py
git commit -m "Introduce a single REGION/LANGUAGES config, point ingest and risk/features at it

Previously ingest/config.py and risk/features.py each hardcoded their
own, disagreeing, Srikakulam-specific bbox. Both now import from the
new services/api/config.py, set to Aizawl district, Mizoram."
```

---

### Task 2: Delete dead Srikakulam-only code

**Files:**
- Delete: `services/api/ingest/cyclone.py`
- Delete: `services/api/ingest/sar.py`
- Delete: `services/api/routers/seed.py`
- Delete: `apps/web/src/components/LiveRiskPanel.tsx`
- Modify: `services/api/main.py` (remove `seed` router registration)
- Modify: `services/api/risk/heuristic.py` (remove `DISASTER_WEIGHTS`, `disaster_type`-shaped `weights` param stays but the multi-hazard dict goes)
- Modify: `services/api/risk/features.py` (remove `disaster_type` parameter and per-type cache path)
- Modify: `services/api/risk/rainfall.py` (remove `fetch_live_rain_72h`, `live_rain_date_range`, `today_iso`, the `_OPEN_METEO_URL` live-forecast block, and the now-unused `json`/`urllib.request`/`date` imports)
- Modify: `services/api/routers/risk.py` (remove `/risk/live`, `/risk/live/range`, the `disaster_type` query params, the `_cells_by_type` dict)
- Modify: `services/api/models.py` (remove `LiveRiskRangeOut`, `LiveRiskOut`)
- Modify: `apps/web/src/lib/api.ts` (remove `DisasterType`, `LiveRiskRangeOut`, `LiveRiskOut`, `liveRisk`, `liveRiskRange`, the `disaster_type` query params on `riskCells`/`riskCell`/`seedTitli`)
- Modify: `apps/web/src/lib/hooks.ts` (remove `useLiveRiskRange`, `useLiveRisk`, the `disasterType` params on `useRiskCells`/`useRiskCellDetail`/`useSeedTitli`)
- Modify: `apps/web/src/App.tsx` (remove the `LiveRiskPanel` import/usage, the `disasterType` state, and whatever selector sets it)
- Test: `services/api/tests/test_router_log.py` and the rest of `services/api/tests/` — must still pass after these deletions

**Interfaces:**
- Consumes: `config.REGION`, `config.LANGUAGES` from Task 1.
- Produces: `risk.features.build_risk_cells() -> list[dict]` (no `disaster_type` param), `risk.features.nearest_risk_score(lat, lon) -> float` (no `disaster_type` param), `risk.heuristic.compute_heuristic_risk(hand, rain_72h, slope_deg, dist_stream_m, drainage_penalty) -> tuple[np.ndarray, dict]` (the `weights` param stays optional, defaulting to the module's single `_WEIGHTS`, since sub-project 3 replaces this module's formula entirely — it is not re-adding the multi-hazard switch).

- [ ] **Step 1: Delete the ingest scripts that only served the flood build**

```bash
git rm services/api/ingest/cyclone.py services/api/ingest/sar.py
```

`cyclone.py` is IBTrACS cyclone-track ingest — meaningless for a landslide hazard. `sar.py`'s own docstring says "for flood labels" and its date constants are the Titli event dates — the NER risk model's labels come from GSI/NASA GLC per `docs/TRAINING.md`, not SAR thresholding.

- [ ] **Step 2: Delete the Titli seed endpoint**

```bash
git rm services/api/routers/seed.py
```

Remove its registration in `services/api/main.py` — delete the `seed` entry from the `from routers import ...` line and the `app.include_router(seed.router, ...)` line.

- [ ] **Step 3: Strip the multi-hazard switch from `risk/heuristic.py`**

Delete the `DISASTER_WEIGHTS` dict (the `cyclone`/`flood`/`urban_flooding`/`landslide` block) entirely. Keep `_WEIGHTS` and `compute_heuristic_risk`'s existing `weights: dict[str, float] | None = None` parameter as-is — a future sub-project replaces the formula, but the optional-override shape is harmless and used by nothing else right now.

- [ ] **Step 4: Strip `disaster_type` from `risk/features.py`**

- `build_risk_cells(force: bool = False)` — remove the `disaster_type` parameter, the `DISASTER_WEIGHTS` validation, and `_cache_path`'s per-type suffix logic (cache always at `CACHE_DIR / "risk_cells_cache.npy"`).
- `nearest_risk_score(lat: float, lon: float) -> float` — remove the `disaster_type` parameter.
- Remove the `_cells_by_type`-style multi-cache helper (`_cache_path`) if nothing else uses it, replacing with a single constant path.
- Remove the now-unused `from risk.heuristic import DISASTER_WEIGHTS` import; keep `band, compute_heuristic_risk`.

- [ ] **Step 5: Remove the live-rainfall functions from `risk/rainfall.py`**

Delete `_OPEN_METEO_URL`, `_fetch_daily`, `live_rain_date_range`, `fetch_live_rain_72h`, `today_iso`. Keep `load_rainfall_dataset` and `rain_window` (or their equivalents) — those read the historical NetCDF and are still needed. Remove the `json`, `urllib.request`, and `date as date_cls` imports if nothing else in the file uses them.

- [ ] **Step 6: Remove the live-risk endpoints from `routers/risk.py`**

Delete `live_risk_range()` and `live_risk()` entirely. Collapse `_cells_by_type: dict[str, list[dict]]` and `_get_cells(disaster_type)` back to a single `_cells: list[dict] | None = None` / `_get_cells()` (matching the original pre-multi-hazard shape). Remove `disaster_type` query params from `list_cells` and `cell_detail`. Remove the now-unused imports (`numpy`, `LiveRiskOut`, `LiveRiskRangeOut`, `DISASTER_WEIGHTS`, `fetch_live_rain_72h`, `live_rain_date_range`, `today_iso`, `_DEMO_CENTER_LON`/`_DEMO_CENTER_LAT` if unused elsewhere).

- [ ] **Step 7: Remove `LiveRiskOut`/`LiveRiskRangeOut` from `models.py`**

Delete both Pydantic models.

- [ ] **Step 8: Delete the frontend live-risk panel and its wiring**

```bash
git rm apps/web/src/components/LiveRiskPanel.tsx
```

In `apps/web/src/lib/api.ts`: remove `DisasterType`, `LiveRiskRangeOut`, `LiveRiskOut`, the `liveRisk`/`liveRiskRange` entries, and the `disaster_type` query param from `riskCells`, `riskCell`, `seedTitli` (and remove `seedTitli` itself if nothing calls the Titli seed anymore — it points at a now-deleted backend endpoint).

In `apps/web/src/lib/hooks.ts`: remove `useLiveRiskRange`, `useLiveRisk`, `useSeedTitli` (its backend endpoint is gone), and the `disasterType` parameter from `useRiskCells`/`useRiskCellDetail`.

In `apps/web/src/App.tsx`: remove the `LiveRiskPanel` import and JSX usage, the `disasterType` state and its setter prop, and any disaster-type selector control that fed it.

- [ ] **Step 9: Run the backend test suite**

Run: `cd services/api && python -m pytest -v`
Expected: PASS (adjust or remove any test that only exercised deleted code — e.g. a test asserting `/risk/live` responds, or asserting `seed_titli` behavior)

- [ ] **Step 10: Verify the frontend still builds**

Run: `cd apps/web && npx tsc --noEmit`
Expected: no type errors. Fix any dangling reference to a removed export before continuing.

- [ ] **Step 11: Grep-verify no stray references remain**

Run: `grep -rn "DISASTER_WEIGHTS\|disaster_type\|DisasterType\|LiveRisk\|seed_titli\|seedTitli\|Titli\|srikakulam\|Srikakulam\|EPSG:32644" services/api apps/web/src --include="*.py" --include="*.ts" --include="*.tsx"`
Expected: no output (aside from files this task doesn't touch that are out of Foundation's scope, e.g. `docs/DEPLOYMENT.md`'s own historical references, which Task 3 handles, or `services/api/data/raw/*` cached files, which are gitignored working files, not code)

- [ ] **Step 12: Commit**

```bash
git add -A services/api apps/web
git commit -m "Delete Srikakulam-only dead code: Titli seed, cyclone/SAR ingest, multi-hazard switch

Per docs/MIGRATION.md #5: the four-hazard disaster-type switch, its
live-rainfall check endpoints and UI panel, the Titli scenario seed,
and the cyclone-track/SAR ingest scripts have no role in a
single-hazard NER build. Committed separately from the region-config
addition so the deletion is independently reviewable."
```

---

### Task 3: Rename `apps/web` to `apps/admin`

**Files:**
- Rename (git mv): `apps/web/` → `apps/admin/`
- Modify: `apps/admin/package.json` (`"name": "web"` → `"name": "admin"`)
- Modify: `apps/admin/Dockerfile`
- Modify: `.dockerignore`
- Modify: `docs/DEPLOYMENT.md`

**Interfaces:** None — this is a path rename with no code-level interface change.

- [ ] **Step 1: Rename the directory with git, preserving history**

```bash
git mv apps/web apps/admin
```

- [ ] **Step 2: Update the package name**

In `apps/admin/package.json`, change `"name": "web"` to `"name": "admin"`.

- [ ] **Step 3: Update `apps/admin/Dockerfile`**

Replace every `apps/web` path reference with `apps/admin` (the `COPY apps/web/package.json ...` and `COPY apps/web /app` lines, and the comment above them referencing the Railway Dockerfile Path setting).

- [ ] **Step 4: Update `.dockerignore`**

Replace `apps/web/dist` and `apps/web/node_modules` with `apps/admin/dist` and `apps/admin/node_modules`.

- [ ] **Step 5: Update `docs/DEPLOYMENT.md`**

Replace the four `apps/web` references (the file-list line, the "aren't needed for this path" note, the Vercel Root Directory instruction, and the `tsc -b` troubleshooting row) with `apps/admin`.

- [ ] **Step 6: Verify the renamed app still builds and runs**

Run: `cd apps/admin && npm install && npm run dev`
Expected: Vite dev server starts with no path-resolution errors. Stop it once confirmed (it's a long-running dev server, not a one-shot check) — `Ctrl+C` or kill the process, don't leave it running as a background task for this step.

Run: `cd apps/admin && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add -A apps .dockerignore docs/DEPLOYMENT.md
git commit -m "Rename apps/web to apps/admin

Matches the target layout in docs/MIGRATION.md and services/api/
BUILD_SPEC.md, done now before packages/ui extraction and a second
client (apps/citizen) make the rename more disruptive."
```

---

### Task 4: Prove the terrain pipeline on a real Aizawl DEM

**Files:**
- Create: `services/api/scripts/verify_aizawl_pipeline.py` (one-off verification script — not part of the ingest layer built in a later sub-project, just today's confidence check)

**Interfaces:**
- Consumes: `config.REGION["bbox"]`, `ingest.dem` (existing DEM-fetch logic — inspect `services/api/ingest/dem.py` before writing this script and reuse its STAC search / sign / mosaic / clip function(s) rather than re-implementing DEM fetch; if `dem.py` only exposes a `fetch()`/`main()` entrypoint rather than an importable function, call that directly instead of duplicating its logic), `risk.terrain.compute_hand`, `compute_slope`, `compute_twi`, `compute_stream_distance` (all take a `dem_path: str`).
- Produces: a real `.tif` under `services/api/data/raw/` for the Aizawl bbox, and console output proving the terrain functions ran against it.

- [ ] **Step 1: Read `services/api/ingest/dem.py` to find its fetch entrypoint**

Run: `cat services/api/ingest/dem.py` (or open it) and identify the function/CLI invocation that performs the Planetary Computer STAC search, sign, mosaic, and clip to `BBOX`, writing a `.tif`. Note its exact name and signature — do not guess it.

- [ ] **Step 2: Run the real DEM fetch against the Aizawl bbox**

Run: `cd services/api && python -m ingest.dem` (or the equivalent entrypoint found in Step 1 — adjust the command to match what actually exists)
Expected: a real network call to Planetary Computer's STAC API, no API key required. Output should print the fetched DEM's shape, resolution, and elevation min/max for the Aizawl bbox `(92.55, 23.55, 93.05, 24.05)`.

**If this fails because the source is unreachable:** stop and report it exactly as it failed. Do not substitute a different DEM source, a different bbox, or cached/synthetic elevation data. This is a hard constraint from `docs/DATA.md` and `CLAUDE.md` §6.

- [ ] **Step 3: Write and run the terrain verification script**

```python
# services/api/scripts/verify_aizawl_pipeline.py
"""One-off confidence check for the NER pivot Foundation sub-project:
does the carried terrain pipeline produce real derived rasters for the
Aizawl bbox? Not part of the ingest layer — DATA.md's ingest/terrain.py
(a later sub-project) is the real, cached, production version of this.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risk.terrain import compute_hand, compute_slope, compute_stream_distance, compute_twi

DEM_PATH = str(Path(__file__).resolve().parents[1] / "data" / "raw" / "dem_aizawl.tif")


def main() -> None:
    print(f"[verify] running terrain derivations against {DEM_PATH}")
    slope = compute_slope(DEM_PATH)
    print(f"[verify] slope: shape={slope.shape}, min={slope.min():.2f} deg, max={slope.max():.2f} deg")

    hand = compute_hand(DEM_PATH)
    print(f"[verify] HAND: shape={hand.shape}, min={hand.min():.2f} m, max={hand.max():.2f} m")

    twi = compute_twi(DEM_PATH) if callable(compute_twi) else None
    if twi is not None:
        print(f"[verify] TWI: shape={twi.shape}")

    dist_stream = compute_stream_distance(DEM_PATH) if callable(compute_stream_distance) else None
    if dist_stream is not None:
        print(f"[verify] dist_stream_m: shape={dist_stream.shape}, max={dist_stream.max():.1f} m")

    print("[verify] pipeline confirmed working on real Aizawl terrain.")


if __name__ == "__main__":
    main()
```

Note: check the actual signatures of `compute_twi` and `compute_stream_distance` in `services/api/risk/terrain.py` before running this — the plan assumes they match `compute_hand`/`compute_slope`'s `(dem_path: str) -> np.ndarray` shape based on `risk/features.py`'s existing calls to them (`compute_twi(DEM_PATH)`, `compute_stream_distance(DEM_PATH)`), but confirm rather than assume.

Run: `cd services/api && python scripts/verify_aizawl_pipeline.py`
Expected: real, non-placeholder shape/min/max numbers printed for every function, no exceptions.

- [ ] **Step 4: Report the result plainly**

State the printed numbers in the handoff to the user — real elevation range, real slope range, real HAND range for Aizawl. This is the actual confidence check from `docs/MIGRATION.md` §8 step 2, not a simulated one.

- [ ] **Step 5: Commit**

```bash
git add services/api/scripts/verify_aizawl_pipeline.py
git commit -m "Add a one-off verification script proving the terrain pipeline runs on a real Aizawl DEM

Confirms the migration thesis: the carried HAND/slope/TWI/stream-
distance pipeline needs no code change beyond the region-constant
swap from Task 1 to produce real derived rasters for Aizawl district."
```

(Do not commit the fetched `.tif` itself — `services/api/data/raw/*.tif` is gitignored, matching the existing pattern for `srikakulam_dem.tif` before it.)
