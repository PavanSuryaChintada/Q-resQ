# PRD — Q-ResQ NER

**Smart India Hackathon 2026 · Problem Statement 26001**
**Ministry of Development of North Eastern Region · Theme: Disaster Management**
**Demo geography: Aizawl district, Mizoram · Build window: 6 days**

---

## 1. Why Aizawl

The problem statement names landslides, flash floods, road blockages, slope failures, fragile terrain, and **unplanned hill cutting**. Aizawl is where all six co-occur most acutely.

The city is built on steep ridge slopes. Construction proceeds by cutting into hillsides, and cut faces are among the most common failure surfaces in the region. Monsoon rainfall is heavy and sustained. When a slope fails on a ridge road, settlements below and beyond are cut off — often for days — which is precisely the isolation problem the brief describes.

It is also tractable in six days: a single district, good Sentinel-1 coverage, and a manageable DEM footprint.

---

## 2. The framing

Most landslide early-warning systems infer risk from rainfall and terrain and stop there. They tell you a slope is the *kind* of slope that fails.

They do not tell you that this particular slope is **currently moving**.

Satellite InSAR does. Precursory accelerating displacement is detectable ahead of catastrophic slope failures that were otherwise entirely unforeseen, at a cost per slope far below dedicated ground instrumentation. That is the core of what we build.

And when a slope does fail, a second problem begins: roads are blocked, settlements are isolated, and a limited response capacity must be allocated. We solve that too.

> **Everyone predicts landslides from rainfall. We watch the slope actually moving — and then decide who gets reached first when the road goes.**

---

## 3. Users

**District administration / DDMA officer.** Desktop. Needs the risk surface, deformation trends, road status, citizen reports, and a response plan. Not technical. Will be asked afterwards to justify every decision.

**Field official.** Mobile, intermittent connectivity. Verifies citizen reports, updates road status, logs completion.

**Citizen in a hill settlement.** Mobile, often no signal. Needs alerts in their own language, and the ability to report a crack or a blocked road and trust it will send.

---

## 4. Scope

### Mapped against the problem statement

| PS requirement | What we ship |
|---|---|
| Rainfall patterns | IMD gridded product + Open-Meteo; antecedent 1/3/7/15 d + intensity |
| Soil moisture sensors | **Satellite** (SMAP, ERA5-Land) + documented sensor ingest contract |
| Satellite imagery | Sentinel-1 SAR; **InSAR deformation** is the headline |
| Terrain / slope data | Copernicus DEM 30 m → slope, aspect, curvature, HAND, TWI, LS |
| Historical landslide records | GSI inventory + NASA Global Landslide Catalog as training labels |
| AI/ML high-risk zones | LightGBM susceptibility + deformation-triggered alerting |
| Real-time alerts | CAP payload generation, geo-fenced, multilingual |
| GIS mapping | MapLibre; vulnerable roads, settlements, infrastructure |
| Citizen geo-tagged uploads | Citizen PWA with on-device pre-classification |
| Risk severity dashboard | Admin console, IMD warning ladder |
| Road connectivity status | Blockage-aware road graph, live component analysis |
| Weather-linked forecasts | Forecast rainfall → forward risk projection |
| Response prioritisation | QUBO dispatch engine (carried over) |
| Multilingual | Hindi, Assamese, English at demo scope |
| Offline / low-network | PWA, cached tiles, IndexedDB queue, idempotent sync |

### Explicitly out of scope

State these as decisions when asked. They are not oversights.

- **SMS gateway delivery.** CAP payloads are generated and displayed. Wiring to a gateway needs credentials and procurement, not engineering.
- **In-situ sensor hardware.** We have none. We will not simulate a feed.
- **Live InSAR processing.** Pre-computed for the demo corridor. See §6.
- **All eight NER states.** One district, done properly.
- **Native iOS.** Android via Capacitor from the same PWA source.
- **Any language beyond English, Hindi, Assamese.** The i18n structure supports more; we do not generate unverified translations of emergency instructions without a native speaker to check them — Mizo included, despite it being the demo geography's local language.

---

## 5. Features

**F1 · Landslide susceptibility surface**
LightGBM over terrain, geology, land cover, road-cut proximity, and antecedent rainfall. Per-cell feature attribution. Provenance label on every cell — learned model or physical index.

**F2 · Deformation monitoring**
Per-point line-of-sight velocity and acceleration from InSAR time series over the demo corridor. Acceleration is the early-warning signal: steady creep is normal, acceleration is not.

**F3 · Road connectivity and isolation**
Live graph analysis. Which roads are blocked, which settlements are cut off, and how large each isolated component is.

**F4 · Citizen reporting**
Geotagged photo and video, on-device pre-classification, offline queue, spatial-temporal deduplication, admin triage queue.

**F5 · Geo-fenced multilingual alerts**
CAP-format generation, severity-banded, targeted by polygon, templated per language (English, Hindi, Assamese).

**F6 · Response prioritisation**
Severity scoring including the isolation term, then QUBO-based allocation of response units. Runs on classical solvers; formulation is hardware-ready for quantum backends.

**F7 · Admin console**
Risk map, deformation panel, report triage, road status, dispatch view, append-only ops ledger.

**F8 · Offline capability**
Cached district tiles, queued submissions, background sync, idempotent replay.

---

## 6. The InSAR position — read this before pitching

**What we do:** process Sentinel-1 SLC pairs into an SBAS deformation time series for one corridor in Aizawl, offline, ahead of the demo. Serve it through the API. Show velocity, acceleration, and the per-point series.

**What we do not do:** process on demand. Live SBAS is days of compute plus days of toolchain learning, and we had six.

**What we say, verbatim:**
> "Deformation is pre-computed for the demo corridor. The processing pipeline is in the repository and documented. Running it live is a compute-scheduling problem, not an algorithmic one — and in operational deployment you would schedule it against the Sentinel-1 revisit cycle anyway, not on demand."

That last clause is true and it is the strongest part of the answer. Sentinel-1 revisits on a fixed cadence; there is no operational reason to process on request.

**Do not** fabricate deformation values for corridors that were not processed. If the map shows deformation, it was measured.

---

## 7. Success criteria

**Must be true at demo:**
- Risk surface renders for Aizawl district with per-cell attribution
- Deformation corridor shows real measured velocities and a per-point time series
- A citizen report submitted offline appears in the admin queue after reconnection
- Blocking a road visibly changes which settlements are marked isolated
- Response prioritisation returns a valid allocation with the isolation term visibly affecting order
- Alerts render in three languages (English, Hindi, Assamese)
- The system runs with the quantum toolchain uninstalled

**Judged on:**
- Evidence we read the brief — every PS bullet is addressed or explicitly scoped out
- Honest data provenance — learned versus index, measured versus modelled, shown per cell
- Deployability — no fabricated sensors, no fake gateways, no live claims we cannot support
- The isolation insight, which is specific to this hazard and which most teams will miss

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| InSAR toolchain consumes the week | Hard cutoff day 4. Ship pre-computed corridor regardless. |
| GSI inventory access is slow | NASA Global Landslide Catalog as primary; GSI as enrichment if it arrives. |
| Capacitor Android build fails | PWA is the deliverable; `.apk` is a bonus. Do not let it block. |
| Presence-only labels overfit to "steep" | Careful negative sampling. Report feature importances and check slope is not carrying the whole model. |
| Two clients diverge | Extract `packages/ui/` early, before divergence is possible. |
| Six days, three people, large scope | `docs/WORKFLOW.md` cuts in a defined order. Follow it. |
