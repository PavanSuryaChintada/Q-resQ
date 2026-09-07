# Q-ResQ NER

**AI-based landslide early warning and risk monitoring for the North Eastern Region.**

Smart India Hackathon 2026 · Problem Statement 26001 · Ministry of DoNER
Team Qtron · RGUKT Srikakulam

Demo geography: **Aizawl district, Mizoram**

This is a pivot of [Q-resQ](docs/MIGRATION.md), a flood-dispatch platform originally built for Srikakulam district, Andhra Pradesh. About 60% of the codebase carries over — see `docs/MIGRATION.md` for exactly what.

---

## The idea

Most landslide early-warning systems infer risk from rainfall and terrain, and stop there. They tell you a slope is the *kind* of slope that fails.

They do not tell you that this particular slope is **currently moving**.

Satellite interferometry does. Sentinel-1 InSAR detects precursory accelerating displacement before catastrophic slope failures — including failures that were otherwise entirely unforeseen — at a cost per slope far below in-situ instrumentation.

And when a slope does fail, a second problem starts. Roads close. Settlements are cut off. A limited response capacity has to be allocated across them. We solve that too.

> **Everyone predicts landslides from rainfall. We watch the slope actually moving — and then decide who gets reached first when the road goes.**

---

## What it does

| | |
|---|---|
| **Susceptibility** | LightGBM over terrain, geology, land cover, and proximity to road cuts. Per-cell feature attribution. |
| **Deformation** | InSAR line-of-sight velocity and acceleration per point. Acceleration — not velocity — is the warning signal. |
| **Roads and isolation** | Live graph analysis. Which settlements lose every route out when a road goes. |
| **Citizen reporting** | Geotagged photo and video, on-device pre-classification, offline queue, spatial-temporal clustering. |
| **Alerts** | CAP-format, geo-fenced, three languages (English, Hindi, Assamese), evaluated on-device so they work with no signal. |
| **Prioritisation** | Severity scoring including isolation, then QUBO-based allocation. |

---

## The isolation insight

In a flood, people can often self-evacuate. On a ridge, a single blocked road removes every route out.

Isolation is therefore not a proxy for hazard exposure — it is an independent axis of urgency, specific to this hazard's mechanism. A settlement of forty people with no remaining path to the district headquarters can outrank a larger settlement that still has a road.

It enters the priority score directly, as its own term.

---

## Honest positioning

**Deformation is pre-computed** for the demo corridor. The processing pipeline is in this repository and documented. Running it live is a compute-scheduling problem, not an algorithmic one — and in operational deployment you would schedule against the Sentinel-1 revisit cycle, not on demand.

**We have no in-situ sensors.** Soil moisture comes from satellite (SMAP, ERA5-Land). A sensor ingest contract is documented and ready. We did not simulate hardware we do not have.

**Alert delivery is out of scope.** CAP payloads are generated and displayed. Wiring to an SMS gateway needs credentials and procurement, not engineering.

**Every risk cell is labelled by provenance** — learned model or physical index — in the API and in the UI.

**Languages are English, Hindi, and Assamese.** The i18n structure supports more, but we do not ship unverified translations of emergency instructions — Mizo included — without a native speaker to check them.

Response prioritisation is formulated as a QUBO and runs on classical solvers today. The formulation is hardware-ready for quantum backends. It is not in the critical path; the system runs with the quantum toolchain uninstalled.

---

## Stack

**Clients** Vite · React · TypeScript · Tailwind · MapLibre GL · PMTiles · Workbox · Capacitor (Android) · react-i18next · onnxruntime-web

**Backend** FastAPI · Python 3.11 · Pydantic v2 · Supabase (Postgres 15 + PostGIS + Realtime)

**Geospatial** Copernicus DEM GLO-30 · rasterio · pysheds · richdem · osmnx · networkx

**Models** LightGBM · MobileNetV3 (ONNX)

**InSAR, offline** ISCE2 · MintPy · Sentinel-1 SLC via ASF

**Optimization** OR-Tools CP-SAT · Qiskit + Aer

---

## Repository

```
docs/MIGRATION.md   what carries from the previous build — READ FIRST
docs/PRD.md         scope, users, PS requirement mapping
docs/TRD.md         technical specification
docs/WORKFLOW.md    flows and the six-day build plan
docs/DATA.md        datasets and the ingest prompt
docs/TRAINING.md    data -> features -> models -> export
docs/DESIGN.md      design tokens, carried unchanged

packages/qubo-dispatch/   optimization library, MIT, carried unchanged
packages/ui/              shared components for both clients
services/api/             terrain · risk · insar · roads · reports · alerts · dispatch
apps/admin/               district operations console
apps/citizen/             PWA + Android
```

---

## Running it

```bash
# Database
psql $DATABASE_URL -f services/api/schema.sql

# API
cd services/api && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Data
python -m ingest.run_all

# Admin console
cd apps/admin && npm install && npm run dev

# Citizen app
cd apps/citizen && npm install && npm run dev
npx cap sync android      # for the .apk
```

InSAR processing runs separately, in its own conda environment, offline. See `docs/TRD.md` §5.

---

## Attribution

Copernicus DEM (© DLR, © Airbus DS) · Sentinel-1 (Copernicus, ESA) · ESA WorldCover · OpenStreetMap contributors (ODbL) · NASA Global Landslide Catalog · NASA SMAP · Geological Survey of India · India Meteorological Department
