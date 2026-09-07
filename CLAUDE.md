# CLAUDE.md — Build Rules for Q-ResQ NER

> Read this file completely before writing any code. It overrides your defaults.
> Full specs are in `docs/`. Start with `docs/MIGRATION.md` — this is a pivot of an
> existing codebase, not a new build.

---

## 1. What this is

**Q-ResQ NER** — AI-based landslide early warning and risk monitoring for the North Eastern Region.

**Smart India Hackathon 2026 · Problem Statement 26001 · Ministry of DoNER**

This is a pivot of an existing flood-dispatch platform (Q-ResQ, built for Srikakulam district). Roughly 60% of the codebase carries over. `docs/MIGRATION.md` states exactly what carries, what is retrained, and what is new. **Read it before touching anything.**

**Demo geography:** Aizawl district, Mizoram.
**Time budget: 6 days.** Every scope decision in these docs follows from that.

---

## 2. The three hard scope calls

These are decisions, not oversights. If you find yourself building past them, stop.

### 2.1 InSAR is PRE-COMPUTED, not live

Live SBAS interferometric processing takes days of compute and days of learning ISCE2/MintPy. It will not happen in six days.

**What we ship:** a deformation time series for **one corridor** in Aizawl, processed offline, loaded as a static dataset, and served through a live-looking API. The pipeline code exists and is documented; it just is not run on demand.

**What we say:** "Deformation time series pre-computed for the demo corridor. The processing pipeline is in the repo; live processing is a compute-scheduling problem, not an algorithmic one."

Never claim live InSAR. Never fabricate deformation values for corridors that were not processed.

### 2.2 One codebase for the citizen app

PWA built with Vite, wrapped for Android with **Capacitor**. Not React Native. Not a second codebase.

This gives a real installable `.apk` from the same source in about two hours of setup. If you find yourself writing Android-specific screens, stop — that is the wrong path for this timeline.

### 2.3 Quantum is present, wired, and not the headline

The `qubo-dispatch` package carries over unchanged. It is wired to the response-prioritisation feature, which is bullet (f) of the problem statement.

**It is mentioned once, in one place, and never leads.** SIH is judged by ministry and industry panels who asked for a landslide monitoring system, not a quantum demo. The headline is InSAR deformation monitoring.

Framing, verbatim, wherever it appears:
> "Response prioritisation is formulated as a QUBO and runs on classical solvers today. The formulation is hardware-ready for quantum backends. It is not in the critical path."

Never claim quantum advantage. Never put "quantum" in a heading, a nav item, or a slide title.

---

## 3. Non-negotiable rules

- **No gradients, glassmorphism, purple, glow, or border-radius above 2px.** `docs/DESIGN.md` carries over from the previous build unchanged. Read it before writing CSS.
- **No fabricated sensor data.** We have no in-situ hardware. Satellite soil moisture only, plus a documented sensor ingest contract. Do not simulate a sensor feed.
- **The system works offline.** Not as a feature flag — as the default assumption. NER connectivity is poor and the problem statement names this explicitly.
- **Every risk score is labelled by provenance.** Learned model or physical index, shown per cell. Never blur the distinction.
- **Two clients, one backend.** Shared auth, shared API, shared component library. Do not build two systems.
- **Languages: English, Hindi, Assamese only.** The i18n structure supports more, but no other language — Mizo included — is ever generated. There is no native speaker on the team to verify emergency instructions, and unverified translations of emergency messaging do not ship.

---

## 4. Repository layout

```
qresq-ner/
├── CLAUDE.md
├── README.md
├── docs/
│   ├── MIGRATION.md        # READ FIRST — what carries, dies, is new
│   ├── PRD.md
│   ├── TRD.md
│   ├── WORKFLOW.md         # 6-day build plan
│   ├── DATA.md             # NER datasets + ingest prompt
│   ├── TRAINING.md         # model training spec + prompt
│   └── DESIGN.md           # carried over unchanged
├── packages/
│   ├── qubo-dispatch/      # CARRIES UNCHANGED — do not modify
│   └── ui/                 # NEW — shared components for both clients
├── services/
│   └── api/
│       ├── schema.sql          # runnable — source of truth for the DB
│       ├── BUILD_SPEC.md       # implementation contract
│       ├── terrain/        # carries, extended
│       ├── insar/          # NEW
│       ├── risk/           # retrained
│       ├── roads/          # NEW — not carried, see docs/MIGRATION.md §2
│       ├── reports/        # NEW — citizen submissions
│       ├── alerts/         # NEW — CAP generation
│       └── dispatch/       # carries
└── apps/
    ├── BUILD_SPEC.md       # implementation contract for both clients
    ├── admin/              # evolved from previous web client
    └── citizen/            # NEW — PWA + Capacitor
```

---

## 5. Stack

Everything below is either carried over or a deliberate addition. Do not add libraries not listed without stating why.

**Carried unchanged:** Vite · React · TypeScript · Tailwind · MapLibre GL · PMTiles · Workbox · idb · FastAPI · Pydantic v2 · Supabase (Postgres + PostGIS + Realtime) · LightGBM · rasterio · osmnx · networkx · Qiskit + Aer · OR-Tools

**New:**
- `@capacitor/core`, `@capacitor/android`, `@capacitor/geolocation`, `@capacitor/camera` — Android wrap
- `react-i18next` — multilingual (English, Hindi, Assamese)
- `MintPy` / `ISCE2` — InSAR processing (offline only, not in the API path)
- `onnxruntime-web` — on-device photo classification in the citizen app
- `python-multipart`, `Pillow` — media upload handling

---

## 5b. Where the implementation contracts live

Read the relevant spec before writing code in that area:

- `docs/MIGRATION.md` — what carries, what is retrained, what is new. **First.**
- `services/api/BUILD_SPEC.md` — backend, file by file, with the traps.
- `services/api/schema.sql` — runnable. Apply with psql; never retype DDL.
- `apps/BUILD_SPEC.md` — both clients, shared UI package, Capacitor.
- `docs/TRAINING.md` — data → features → models → export. **Its §0 lists three
  failure modes that produce models which look excellent and are worthless.
  Read it before writing any training code.**

## 6. When you are unsure

Ask rather than assume. If a spec in `docs/` conflicts with this file, this file wins. Stop and ask before adding a dependency, inventing a colour, adding a feature, claiming a performance result, or building anything that contradicts §2. If a data source is unreachable, say so — never substitute a different source, region, or date range without saying so first.
