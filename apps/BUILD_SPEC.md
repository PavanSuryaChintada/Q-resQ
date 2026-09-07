# BUILD SPEC — apps/

Implementation contract for both clients. Read `../CLAUDE.md` and `../docs/DESIGN.md` first — the design tokens carry over unchanged and the ban list is enforced.

**Two clients, one backend, one shared component package.** Do not build two systems.

---

## Build order

```
1. packages/ui/           extract early — before divergence is possible
2. apps/admin/             renamed from apps/web, evolve the existing console
3. apps/citizen/           new PWA, built against the real reports endpoint
4. Capacitor wrap          two hours, cut if it fights you
```

Extracting `packages/ui` early is not premature abstraction. If both clients grow their own button, map wrapper, and severity chip, merging them later costs more than the extraction did.

`apps/citizen`'s capture flow depends on `services/api/reports/` already existing (`services/api/BUILD_SPEC.md` §5 comes before this file's §3) — the client is written against a real endpoint, not a mock.

---

## 1. `packages/ui/`

Extracted from the existing admin components.

```
packages/ui/src/
├── tokens.css          # from docs/DESIGN.md — do not edit values
├── Map/                # MapLibre wrapper, layer registry, PMTiles loader
├── SeverityChip.tsx    # IMD ladder, 12px square, no radius, no pill
├── RiskLegend.tsx
├── Button.tsx  Input.tsx  Select.tsx
├── i18n.ts             # react-i18next provider + locale loader
└── offline/
    ├── queue.ts        # IndexedDB via idb — SHARED by both clients
    └── sync.ts         # batch flush, idempotent on client uuid
```

`offline/` is shared deliberately. Both clients queue submissions offline against the same contract, and having one implementation means one set of bugs.

---

## 2. `apps/admin/` — district console

Desktop. Renamed from `apps/web` in the Srikakulam build; evolves from there.

### Carried unchanged
Risk map, request queue, dispatch view, append-only ops ledger, layer toggles, cell detail panel.

### New panels

**Deformation**
- Corridor boundary drawn on the map. Outside it the layer is empty and the UI says "not processed" — never blank ambiguity.
- Points coloured by `alert_state`: stable, creeping, **accelerating**.
- Click a point -> displacement time series chart, plus `n_acquisitions` and date range.
- **Accelerating points sort to the top of any list and are the only ones that get a severity colour.** Creeping is not an alert; the whole value of the feature is that distinction.

**Report triage**
- Ordered by cluster size x auto-confidence x area risk
- **Clusters, not individual reports.** Expand a cluster to see its members.
- Media thumbnails, never full resolution in the list
- Verify / dismiss / mark duplicate. Verifying a `road_blocked` report sets `road_segments.blocked` with source `confirmed`.

**Road status and isolation**
- Blocked segments dashed, coloured by source: predicted, reported, confirmed
- Isolated settlements marked, with population and component size
- **A button to block the demo's named ridge segment.** Deterministic, triggered on cue — the backend behind it (`services/api/roads/isolation.py`) is built and tested well before this UI wraps it.

### Risk map provenance

Every cell carries `provenance`. Cells scored by the learned model and cells scored by the physical index must be visually distinguishable — a hatch pattern or a border, not a different hue, because hue is reserved for severity.

This is not pedantry. It is the visible expression of the honesty position, and a judge who notices it will trust everything else more.

---

## 3. `apps/citizen/` — PWA + Android

Mobile-first. Vite + React + Capacitor.

```
apps/citizen/src/
├── routes/
│   ├── Home.tsx          # my risk + active alerts
│   ├── Report.tsx        # capture -> classify -> queue
│   ├── MyReports.tsx     # local queue + sync status
│   └── Help.tsx          # request assistance
├── lib/
│   ├── classifier.ts     # onnxruntime-web, on-device
│   ├── geofence.ts       # cached fences, evaluated locally
│   └── camera.ts         # Capacitor Camera + web fallback
└── locales/{en,hi,as}.json
```

### Report flow

```
capture photo (Capacitor Camera, or <input capture> on web)
   |
read EXIF GPS -> fall back to device geolocation
   |
run ONNX classifier on-device (works offline)
   |
queue in IndexedDB with client-generated UUID
   |
show "queued - will send when you have signal"
   |
on reconnect: batch POST /reports/sync
```

**Offline-first from the first commit.** Do not build the online path and retrofit offline — the retrofit always leaks, and NER connectivity is the reason this feature exists.

### On-device classifier

`onnxruntime-web`, WASM backend, model under 10 MB. Runs with no network.

Present it as **triage assistance, never detection**. The label in the UI is "we think this looks like: crack" with the option to correct it, not "landslide detected". Report real accuracy if asked.

### Geo-fenced alerts

Fences are fetched when online and cached. Evaluation happens on-device against the cached set, so alerts work with no signal. This is the point — the moment connectivity fails is the moment an alert matters most.

### Location consent

- Explicit opt-in with a plain-language explanation of what it is used for
- **Foreground only.** No background tracking.
- Revocable from settings
- The app must remain useful with location denied — manual map pin for reports

A ministry panel will ask about this. Have the answer built, not just written.

### Languages

**English, Hindi, Assamese only.** `react-i18next`, JSON per locale, keyed strings. No other language — Mizo included, despite it being the demo geography's local language — is generated without a native speaker available to verify emergency instructions. The i18n structure supports adding more later.

**No concatenated strings anywhere.** `t('alert.evacuate', {settlement})`, never `t('alert.prefix') + name`. Concatenation produces ungrammatical output in every language whose word order differs from English.

Language selection on first launch, changeable later, persisted locally.

---

## 4. Capacitor — Android

**Two hours. Timeboxed.**

```bash
npm i @capacitor/core @capacitor/cli
npm i @capacitor/android @capacitor/geolocation @capacitor/camera
npx cap init "Q-ResQ" "in.qtron.qresq" --web-dir=dist
npm run build && npx cap add android && npx cap sync
npx cap open android      # build the .apk in Android Studio
```

`AndroidManifest.xml` needs: `INTERNET`, `ACCESS_FINE_LOCATION`, `CAMERA`, `READ_MEDIA_IMAGES`.

**If it fights you past two hours, ship the PWA.** It installs from the browser, it works offline, and it is the deliverable. The `.apk` is a bonus and it is cut #8 in `docs/WORKFLOW.md` §6.

---

## 5. Design enforcement

`docs/DESIGN.md` carries unchanged. Hard bans, no exceptions:

- No gradients — no `linear-gradient`, no `bg-gradient-to-*`
- No glassmorphism, no `backdrop-filter`
- No purple, violet, or indigo
- No glow, no coloured `box-shadow`
- No `border-radius` above 2px
- No emoji in the UI
- Colour encodes severity only; everything else is greyscale

The IMD warning ladder is the only chromatic vocabulary. It is a government standard officers already read, which is why it is defensible rather than decorative.

**Severity is never encoded by colour alone.** Always pair with a numeral or a text band label. An emergency system that fails for a colour-blind officer is a broken emergency system.

Do a dedicated pass on the last day hunting for violations. They creep in.

---

## 6. Copy

Sentence case. Active voice. Plain verbs.

| Write | Not |
|---|---|
| Report sent | Success! |
| Queued - will send when you have signal | Offline mode active |
| No signal. Your report is saved. | Network error |
| 3 settlements have no route out | Isolation detected |
| We think this looks like: crack | Landslide detected |
| This slope is moving faster than before | Anomaly detected |

Errors state what happened and what to do. Empty states are instructions.

Never write: leverage, seamless, powerful, cutting-edge, revolutionise, harness, empower.

---

## 7. Tests

```
test_sync.ts        # replayed offline batches produce no duplicate rows
test_queue.ts       # queue survives page reload and app restart
test_geofence.ts    # fence evaluation is correct with no network
test_i18n.ts        # every key exists in all three locales (en, hi, as)
```

`test_i18n.ts` catches the failure where a language silently falls back to English mid-screen, which looks far worse in a demo than not supporting the language at all.
