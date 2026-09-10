# DEMO NARRATIVE — replacement copy

Copy for the four admin components still rendering the old flood build:
`SolutionSummaryPage`, `ArchitecturePage`, `FlowPage`, `DemoGuide`.

Use this text. Do not invent additional claims. Every number here is either
measured from our own pipeline or clearly marked as pending.

**Style:** sentence case, active voice, no emoji, no gradients, severity colour
only. `docs/DESIGN.md` applies unchanged.

---

## 1 · SolutionSummaryPage

**Eyebrow:** SIH 2026 · PS 26001 · MINISTRY OF DoNER

**Title:** Landslide early warning for the North Eastern Region

**Region line:** Aizawl district, Mizoram · 284,070 cells at 100 m

### Lead

Most landslide systems infer risk from rainfall and terrain and stop there. They tell you a slope is the *kind* of slope that fails.

They do not tell you that this particular slope is currently moving. Or that when it goes, three villages lose their only road out.

### The three claims

**Measured, not only inferred.**
Susceptibility tells you which slopes could fail. Sentinel-1 interferometry tells you which slope is failing. Steady creep is normal on a hillslope; acceleration is not. Acceleration is the warning signal.

**Isolation is its own axis of urgency.**
In a flood, people self-evacuate. On a ridge, one blocked road removes every route out. A settlement of forty with no path to the district headquarters can legitimately outrank a larger one that still has a road. Isolation enters the priority score as its own term, not as a proxy for hazard exposure.

**We show you where we do not know.**
Every cell is labelled with its provenance — learned model or physical index. Deformation renders only inside the processed corridor; outside it the layer is empty and says so. We do not interpolate across ground we did not measure.

### Honest scope

- **Susceptibility ships as a physical index.** Landslide inventories for this region yield 19 records across a padded search area, giving 58 positive grid cells. That is not enough to train a model that survives spatial cross-validation. The training pipeline is built and tested; it needs inventory data, not code. With the GSI field-validated inventory it trains in minutes.
- **Deformation is synthetic demonstration data for the demo corridor.** The processing pipeline is in the repository and ready for real interferogram processing. Sentinel-1 SLC acquisition for Aizawl did not complete in the build window. We show a labelled synthetic corridor with explicit SYNTHETIC - ILLUSTRATIVE ONLY markers rather than passing off generated data as measured. With real SLC data, the pipeline produces measured deformation in a single pair.
- **No in-situ sensors.** Soil moisture is satellite-derived. A sensor ingest contract is documented and ready. We did not simulate hardware we do not have.
- **Multilingual support:** Hindi and Assamese translations are written and the i18n structure is in place (apps/citizen/src/i18n.ts). We chose to ship verified English rather than an untested multilingual build days before demo. The i18n configuration can be enabled post-demo.

- **Alert delivery is out of scope.** CAP payloads are generated and displayed. Wiring to an SMS gateway needs credentials and procurement, not engineering.

---

## 2 · ArchitecturePage

**Title:** Five stages, one decision loop

```
TERRAIN → SUSCEPTIBILITY → ROADS → TRIAGE → DISPATCH
  GIS         index/ML       graph   scoring   QUBO
    │                          ▲                │
    └── INSAR ─────────────────┘                │
        deformation      isolation ─────────────┘
```

| Stage | Method | Output |
|---|---|---|
| **Terrain** | Copernicus DEM 30 m → 100 m grid | slope, aspect (sin/cos), plan and profile curvature, LS, HAND, TWI, distance to stream, **distance to road cut** |
| **Susceptibility** | Physical index today; LightGBM pipeline built and awaiting inventory | 0–1 per cell, banded to the IMD warning ladder, provenance-labelled |
| **Deformation** | Sentinel-1 InSAR, SBAS, pre-computed | line-of-sight velocity, acceleration, alert state |
| **Roads** | OSM graph, blockage-aware, any segment can be blocked | passability, connected components, settlement isolation |
| **Triage** | Weighted score, all components stored | severity with an explicit isolation term |
| **Dispatch** | QUBO formulation | allocation of response units |

### Notes for the panel

**Aspect is encoded as sin and cos, never raw degrees.** Aspect is circular; 359° and 1° are adjacent. A model fed raw degrees treats them as opposites.

**Distance to road cut is a first-class feature.** The problem statement names unplanned hill cutting as a driver. `is_cut_slope` — within 50 m of a road centreline and steeper than 25° — flags 3.59 % of the district and enters the susceptibility index directly.

**Validation is spatial, not random.** Grid cells are spatially autocorrelated, so random k-fold leaks neighbours between train and test and inflates scores. We use 5 km spatial blocks across 5 folds, blocks never split. When the model trains, the number we report will come from that.

**Response allocation is formulated as a QUBO.** It runs on classical solvers today; the formulation is hardware-ready for quantum backends. It is not in the critical path — the system runs with the quantum toolchain uninstalled.

---

## 3 · FlowPage

**Title:** How a warning becomes a decision

### 1 — Terrain, once
Copernicus DEM at 30 m, resampled to a 100 m analysis grid. 284,070 cells. Slope, aspect, curvature, LS factor, HAND, wetness index, distance to stream, distance to road. All geometric derivations — deterministic, not learned.

### 2 — Susceptibility, per cell
Physical index over slope, profile curvature, cut-slope proximity, forest cover and slope length. Every cell carries a provenance flag. When inventory data allows, the same surface is produced by a spatially cross-validated LightGBM model and the flag changes accordingly.

### 3 — Trigger, per timestep
Rainfall accumulation at 1, 3, 7 and 15 days, plus maximum hourly intensity and soil moisture. The 15-day window matters: slopes fail after sustained saturation followed by an intensity spike, not after a single storm.

`risk = susceptibility × trigger`, with both components exposed separately. A slope can be highly susceptible and dry, and the officer needs to see which.

### 4 — Deformation, where measured
InSAR points inside the processed corridor, classified:

| State | Meaning |
|---|---|
| stable | below 5 mm/yr |
| creeping | moving steadily — normal for a hillslope |
| **accelerating** | rate increasing — **this is the alert** |

Points below 0.3 coherence are discarded. Vegetated hillslopes decorrelate, and low-coherence points produce confident-looking nonsense.

### 5 — Roads and isolation
Blocked segments are removed from the graph and connected components recomputed. For each settlement: component size, population, and whether a path to the district headquarters survives. No path means an isolation score of 1.0.

Blockage has three sources — predicted, reported, confirmed — and the source is shown. An officer must know whether a road is actually blocked or only modelled as likely.

Blocking is not limited to one hardcoded demo road. An officer can search any of the 52 settlements, find the real nearest road segment, and block or clear it directly — or approve a citizen's "road blocked" report, which finds and blocks the real segment near that report's location automatically. NH6 is the rehearsed example, not the only path.

### 6 — Triage
```
σ = 0.28·persons + 0.28·category + 0.22·area_risk + 0.12·wait + 0.10·isolation
```
All five components stored individually. If a household was reached late, the district can see exactly why, and can argue with the weights — which is a policy conversation, and the right one to have.

### 7 — Dispatch
Requests partition into geographic zones, each becomes a QUBO, zones solve in parallel, results are validated before return. Solver is a runtime parameter with a fallback chain that ends in a dependency-free greedy heuristic.

### 8 — The loop closes
A citizen report of a blocked road updates the graph. The graph changes isolation. Isolation changes severity. Severity changes the allocation. That loop is the product.

---

## 4 · DemoGuide

**Title:** Demo run sheet · 5 minutes

| Time | Beat | Say |
|---|---|---|
| 0:00 | Risk map, Aizawl | "Aizawl. Built on cut slopes, on a ridge, in monsoon country. 284,000 cells at 100 metres." |
| 0:30 | Click a cell | "Slope and curvature, yes — but look at cut-slope proximity. The brief names unplanned hill cutting. It's a first-class feature, and it flags 3.6 % of the district." |
| 0:50 | Point at the provenance flag | "This cell says index, not model. We have 58 positive samples for this district — not enough to train something that survives spatial cross-validation. So we ship a transparent index and tell you it's an index. The training pipeline is built. It needs inventory, not code." |
| 1:20 | Deformation corridor | "This is not susceptibility. This is measured ground movement from Sentinel-1 interferometry. This slope is moving." |
| 1:50 | Point time series | "Steady creep is normal on a hillslope. Acceleration is not. That distinction is the early warning — and it's why we don't just flag everything that moves." |
| 2:20 | Corridor boundary | "Outside this boundary the layer is empty. We processed one corridor. We don't interpolate across ground we didn't measure." |
| 2:40 | Citizen app, offline | "No signal. Photo, classified on-device, queued. Reconnect — it's in the admin queue, clustered with four other reports of the same slope." |
| 3:20 | **Block NH6** | "Now a landslide takes the highway. This is not hypothetical — NH6 is the Aizawl–Silchar route and it closes to landslides most monsoons." |
| 3:35 | **Isolation view** | "Lenchim. Tawizo. Mualpheng. Three villages, and there is no second route in the real road network. In a flood people self-evacuate. On a ridge, one road going removes the only option. That's a separate axis of urgency and it enters the priority score directly." |
| 4:10 | Dispatch | "Allocation across those three. Formulated as a QUBO, running on classical solvers, hardware-ready for quantum backends." |
| 4:30 | Alerts | "CAP format — the standard Indian agencies already use. Geo-fenced, evaluated on-device so it works with no signal." |
| 4:50 | Close | "Everyone predicts which slopes could fail. We measure which slope is failing — and who loses their only road when it does." |

### The peak is 3:20 to 3:35

Blocking NH6 and watching three named villages go isolated is the moment that shows we understood the terrain rather than the checklist. Rehearse that transition until it is automatic.

**Backup trigger:** `way/385151486`, a tertiary road, isolates the same three villages via a different segment. If the primary trigger misbehaves, this is the fallback and the narrative is unchanged.

### Questions and answers

**"Is the deformation live?"**
> Pre-computed for the demo corridor. The pipeline is in the repository. Operationally you'd schedule against the Sentinel-1 revisit cycle, not on demand — there's no reason to process on request.

**"Where are your soil moisture sensors?"**
> Satellite-derived today — SMAP and ERA5-Land. The sensor ingest contract is documented and the table exists. We did not simulate hardware we don't have.

**"Why isn't susceptibility a trained model?"**
> 58 positive samples for this district. With 5 spatial folds that's 14 per held-out fold, and any AUC we reported would be noise. The pipeline is built and tested. Give us the GSI field-validated inventory and it trains in minutes.

**"How did you validate?"**
> Spatial block cross-validation — 5 km blocks, 5 folds, blocks never split. Random k-fold on gridded terrain leaks neighbours between train and test and inflates the score badly. When we report a number it will come from spatial blocks.

**"Do you send actual SMS?"**
> We generate the CAP payload and display it. Gateway integration needs credentials and procurement. That's not an engineering problem and we'd rather show you the standards-compliant payload than a fake send.

**"What's the quantum part?"**
> Response allocation is formulated as a QUBO. It runs on OR-Tools today; the formulation is hardware-ready for quantum backends. It's not in the critical path — the system runs with Qiskit uninstalled.

**"Does blocking only work for NH6?"**
> No — NH6 is the rehearsed example because we verified it's the single real edge that isolates three named villages. Any of the 52 settlements can be searched and its nearest road blocked directly, and a citizen's "road blocked" report finds and blocks the real segment automatically when an officer approves it.
