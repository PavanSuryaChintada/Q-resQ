# WORKFLOW — Q-ResQ NER

System flows and the six-day build plan.

---

## 1. Core loop

```
       Sentinel-1 SLC              rainfall + soil moisture
       (offline, batch)                    (live)
              │                              │
              ▼                              ▼
      ┌───────────────┐              ┌───────────────┐
      │  InSAR SBAS   │              │   TRIGGER     │
      │  velocity +   │              │  antecedent   │
      │  acceleration │              │  1/3/7/15 d   │
      └───────┬───────┘              └───────┬───────┘
              │                              │
              │      ┌──────────────┐        │
              │      │ SUSCEPTIBIL. │◄────────┘
              │      │  LightGBM    │
              │      │  terrain +   │
              │      │  geology +   │
              │      │  road cut    │
              │      └──────┬───────┘
              │             │
              └──────┬──────┘
                     ▼
             ┌───────────────┐
             │  COMPOSITE    │──────► risk map (F1)
             │     RISK      │──────► geo-fenced alerts (F5)
             └───────┬───────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
  ┌──────────┐ ┌──────────┐ ┌──────────┐
  │  ROADS   │ │ CITIZEN  │ │  HELP    │
  │ blocked? │ │ REPORTS  │ │ REQUESTS │
  └────┬─────┘ └────┬─────┘ └────┬─────┘
       │            │            │
       ▼            │            │
  ┌──────────┐      │            │
  │ISOLATION │      │            │
  │  SCORE   │──────┴────────────┤
  └──────────┘                   │
                                 ▼
                          ┌─────────────┐
                          │   TRIAGE    │
                          │ + isolation │
                          └──────┬──────┘
                                 ▼
                          ┌─────────────┐
                          │  DISPATCH   │
                          │    QUBO     │
                          └─────────────┘
```

Two things to notice. Citizen reports feed both road status and the request queue — a report of a blocked road changes the graph, which changes isolation, which changes triage. And the InSAR branch is batch, everything else is live.

---

## 2. Citizen report lifecycle

```
   capture photo
        │
        ▼
   read EXIF GPS --(none)--► device geolocation
        │
        ▼
   on-device ONNX classifier
        │
        ▼
   ┌──────────┐
   │  QUEUED  │  IndexedDB, client UUID, offline
   └────┬─────┘
        │ connectivity
        ▼
   ┌──────────┐
   │ PENDING  │────── clustered by 100 m / 60 min
   └────┬─────┘
        │ admin review
   ┌────┴─────┬───────────┐
   ▼          ▼           ▼
VERIFIED  DISMISSED  DUPLICATE
   │
   ▼
road status update / help request / risk annotation
```

Clustering before the admin sees anything is what makes this usable. Ten photos of one slope failure must arrive as one incident.

---

## 3. Offline sync

```
client generates UUID → IndexedDB {synced: false}
   → reconnect → POST /reports/sync (batch)
   → server UPSERTS on uuid → 200
   → mark synced
```

**Idempotent by construction.** The client makes the ID, the server upserts on it, replay is harmless. There are no conflicts to resolve. One sentence, and it is the whole answer.

Media upload is separate and retried independently — a queued report with a failed media upload still syncs its metadata, and the media follows.

---

## 4. Alert flow

```
risk band change  ───┐
deformation accel ───┼───► generate CAP XML
verified report   ───┘         │
                                ▼
                      evaluate geo-fence
                                │
                                ▼
                      client-side match against
                      cached fences (works offline)
                                │
                                ▼
                      render in user's language
                      (English / Hindi / Assamese)
```

Geo-fences are cached on the citizen client, so alert evaluation works with no signal. This matters: the moment connectivity fails is exactly when an alert is most needed.

---

## 5. Six-day build plan

Three people. Map A/B/C to skill, not to title. In practice, one executor drives most of the sequence directly rather than three fully parallel tracks — independent pieces still proceed in whichever order unblocks work fastest.

- **A** — backend, data pipeline, InSAR
- **B** — admin console
- **C** — citizen client, i18n, Android wrap

### Day 1 — Foundation and proof of carry

- **All:** branch the repo. Do not fork.
- **A:** introduce `services/api/config.py` (the single `REGION` constant — did not exist before this pivot), swap it to Aizawl, refactor `ingest/config.py` and `risk/features.py` to use it. Run the terrain pipeline against a real fetched Aizawl DEM. **This is the day's most important task** — if the carried terrain pipeline produces a DEM-derived surface for Aizawl by lunchtime, the whole migration thesis is proven and everything else is incremental.
- **A:** apply the additive schema once a database exists. Delete everything in `MIGRATION.md` §5 in a separate commit.
- **B + C:** extract `packages/ui/` from the existing admin components. Rename `apps/web` → `apps/admin`. Both clients scaffolded and deploying green, empty.
- **A, in parallel, external to this build:** Sentinel-1 SLC download for the corridor needs to start today via a human registering an Earthdata account — it is large and slow and cannot be rushed later.

### Day 2 — Data, roads, and reports

- **A:** extend terrain — aspect (sin/cos), curvature, LS, `dist_road_m`, `is_cut_slope`. Ingest OSM roads/settlements/facilities. Ingest GSI lithology and the landslide inventory (external — see `docs/DATA.md`).
- **A:** rainfall ingest — IMD gridded product plus Open-Meteo, antecedent windows.
- **A:** **roads/isolation backend** — graph, connected components, settlement scoring, block/clear endpoint. **Build and test the deterministic demo road-block trigger here, today** — not in the Day 6 freeze pass. It is the peak of the demo and needs days of headroom to verify, not hours.
- **A:** **reports backend** — `POST /reports`, `POST /reports/sync`, clustering. Built before the citizen app's capture flow so the app has a real endpoint to integrate against, not a mock.
- **B:** risk map rendering against real terrain output. Layer toggles, cell detail panel. Roads/isolation UI once the backend from today exists.
- **C:** citizen capture flow — camera, EXIF, geolocation, IndexedDB queue, wired against the real reports endpoint from today. **Offline-first from the first commit**, not retrofitted.

### Day 3 — Models and reporting

- **A:** train the susceptibility model. Negative sampling per `TRD.md` §4. **Inspect feature importances before moving on** — if slope carries more than ~40%, fix the sampling.
- **A:** trigger model, composite risk, provenance flags.
- **B:** deformation panel scaffolded against fixture data. Do not wait on the real InSAR output.
- **C:** report sync endpoint integration, i18n scaffold, three locale files (English, Hindi, Assamese).

### Day 4 — InSAR cutoff, alerts

- **A:** InSAR. **Hard cutoff at end of day.** If MintPy has not produced a usable time series, load whatever partial output exists, or a single hand-processed pair, and move on. Do not spend day 5 on this.
- **A:** alerts and CAP generation.
- **B:** report triage queue with media preview and clustering display.
- **C:** ONNX classifier — train MobileNetV3 on scraped crack/road images, export, wire on-device. Timebox to half a day; if accuracy is poor, ship it and say so.

### Day 5 — Integration and Android

- **A:** wire dispatch with the isolation term.
- **B:** road status and isolation view (if not already integrated Day 2-3). Ops ledger. Full admin integration pass.
- **C:** Capacitor Android build. **Two hours. If it fights you past that, ship the PWA.**
- **All, end of day:** first full end-to-end run. Everything wired, nothing polished.

### Day 6 — Freeze and rehearse

- **Morning:** bug fixes only. No new features. Design pass against `DESIGN.md` — hunt every gradient, every radius above 2 px.
- **Midday:** seed the demo scenario. Real coordinates, real rainfall, real deformation, plausible reports. The road-block trigger is already tested from Day 2 — this is a rehearsal of it, not its first run.
- **Afternoon:** rehearse four times end to end. Record a backup video on two laptops and a phone.
- **Anyone idle:** write the README and the licence attribution slide.

---

## 6. Cut order

If you are behind — and you will be — cut in this order. **From the bottom.**

```
KEEP  1. Risk map with attribution         — never cut
      2. Citizen report + offline sync
      3. Road blocking + isolation
      4. Deformation panel (pre-computed)
      5. Multilingual alerts
      6. Dispatch prioritisation
      7. On-device photo classifier
CUT   8. Android .apk (PWA suffices)
```

Items 1 through 4 are the product. Items 5 through 8 are strengthening. Cutting 7 and 8 costs you very little in front of a ministry panel; cutting 3 costs you the insight that distinguishes this build.

---

## 7. Demo script — 5 minutes

| Time | Beat | Say |
|---|---|---|
| 0:00 | Risk map, Aizawl | "Aizawl. Built on cut slopes, on a ridge, in monsoon country." |
| 0:30 | Click a cell, attribution | "Slope and curvature, yes — but look at proximity to road cut. The brief names unplanned hill cutting. The model found it." |
| 1:10 | Deformation corridor | "This is not susceptibility. This is measured ground movement from Sentinel-1 interferometry — this slope is currently moving." |
| 1:40 | Point time series, acceleration | "Steady creep is normal. Acceleration is not. That distinction is the early warning." |
| 2:20 | Citizen app, offline report | "No signal. Photo, auto-classified on-device, queued. Reconnect — and it is in the admin queue, clustered with four other reports of the same slope." |
| 3:10 | Block a road | "Now the road goes. Watch the settlements." |
| 3:25 | Isolation view | "Three settlements just lost every route out. In a flood people self-evacuate. On a ridge, a blocked road removes the only option. That is a separate axis of urgency and it enters the priority score directly." |
| 4:00 | Response prioritisation | "Allocation across those settlements. Formulated as a QUBO, running on classical solvers, hardware-ready for quantum backends." |
| 4:20 | Alerts, three languages | "CAP format — the standard Indian agencies already use. Generated, geo-fenced, evaluated on-device so it works with no signal." |
| 4:45 | Close | "Everyone predicts landslides from rainfall. We watch the slope actually moving — and decide who gets reached first when the road goes." |

**The peak is 3:10 to 3:25.** Blocking a road and watching settlements go isolated is the moment that shows this team understood the hazard rather than the checklist. It was built and tested on Day 2, not assembled the night before — rehearse the transition until it is automatic.

---

## 8. Failure protocol

| If | Then |
|---|---|
| InSAR incomplete by end of day 4 | Ship whatever processed. Even one interferogram pair with a velocity map is real measured data. Say what it is. |
| SLC download does not finish | Use a pre-processed deformation product if one exists for the area; otherwise state the corridor is unavailable and demo the rest. **Do not fabricate points.** |
| GSI inventory inaccessible | NASA Global Landslide Catalog alone. Fewer labels, state it. |
| Capacitor build fails | PWA. It installs from the browser and it is the deliverable. |
| Photo classifier is poor | Ship it, label it triage assistance, report the accuracy. |
| Judge asks about quantum | `CLAUDE.md` §2.3, verbatim. One sentence, then return to the hazard. |
| Judge asks about sensors | "Satellite soil moisture today. Sensor ingest contract documented and ready. We did not simulate hardware we do not have." |
| Judge asks if InSAR is live | `PRD.md` §6, verbatim. The revisit-cycle clause is the strong part. |
| A data source is unreachable | Say so. Never substitute a different source, region, or date range without saying so first. |
