type Status = "done" | "partial" | "planned"

const STATUS_COLOR: Record<Status, string> = {
  done: "#5C8A6E",
  partial: "#C9A227",
  planned: "#6B6862",
}
const STATUS_LABEL: Record<Status, string> = {
  done: "built, live in this app",
  partial: "partly built",
  planned: "not built",
}
const STATUS_PERCENT: Record<Status, string> = {
  done: "100%",
  partial: "40-70%",
  planned: "0%",
}

interface FeatureRow {
  requirement: string
  status: Status
  how: string
  gap?: string
}

const REQUIREMENTS: FeatureRow[] = [
  {
    requirement: "Risk prediction or early-warning mechanism",
    status: "done",
    how: "Terrain risk (height above nearest drainage, topographic wetness index, distance to stream) computed from real Copernicus DEM data via OpenTopography, combined with real rainfall into a 5-band severity heuristic, percentile-normalised so a handful of outlier cells don't wash out the rest of the map. A LightGBM classifier is trained against real historical flood labels as a second model. The Titli replay uses real IMD RF25 rainfall for 11 Oct 2018; the \"live risk check\" panel picks up today's (or any nearby date's) real rainfall from Open-Meteo instead and re-scores the same terrain grid, so selecting today's date does produce a fresh answer.",
    gap: "The live check applies one rainfall reading for the whole demo area rather than interpolating per cell, and only covers roughly a 90-day window around today (Open-Meteo's forecast API range) - an arbitrary date years in the past outside that window returns an honest error, not a fabricated number.",
  },
  {
    requirement: "Interactive map showing vulnerable locations",
    status: "done",
    how: "MapLibre GL map with risk cells coloured by severity band, click-to-inspect detail panel per cell, live request and unit markers, and dispatch routes drawn between them.",
  },
  {
    requirement: "Nearby shelters, hospitals, emergency services, and resources",
    status: "planned",
    how: "Designed to pull hospitals, clinics, fire and police stations, and shelters from OpenStreetMap via the Overpass API.",
    gap: "Every public Overpass mirror tried (the default host plus two fallbacks) was unreachable from this build network - one returned 403 forbidden, the rest timed out. No facilities layer exists on the map.",
  },
  {
    requirement: "Real-time notifications and alerts",
    status: "partial",
    how: "The dispatch ledger panel shows solves, fallbacks, and system events as they happen, polling every 2-4 seconds.",
    gap: "In-app only - there is no push notification, SMS, or alert delivered to a field unit's own device.",
  },
  {
    requirement: "Dashboard for administrators / rescue teams",
    status: "done",
    how: "Full operations dashboard: layers panel, risk-cell detail, units panel, request queue with search and a card-carousel view, dispatch controls with a live solver benchmark, and the dispatch ledger.",
  },
  {
    requirement: "Prioritisation of rescue requests based on severity",
    status: "done",
    how: "Each request's severity is computed from people count, category, area risk, and wait time. The dispatch solver optimises severity times people count against travel time under hard capacity constraints - it never double-books a unit or a request. The request queue is sorted by severity and searchable.",
  },
  {
    requirement: "Offline / low-connectivity functionality",
    status: "planned",
    how: "Designed around IndexedDB for local request queueing and a Workbox service worker for offline asset caching.",
    gap: "Not implemented - cut to protect the risk model and dispatch pipeline given the build window.",
  },
]

const EXTRA_ROWS: FeatureRow[] = [
  {
    requirement: "Which vehicle can actually take a given route",
    status: "partial",
    how: "Every dispatch route on the map is now labelled with the assigned unit's kind and callsign (for example \"BOAT · Boat 04\"), so it's visible at a glance what's being sent where.",
    gap: "This is a label, not a hard constraint - the solver does not yet know which request locations are boat-only versus road-accessible; it optimises purely on severity and travel time.",
  },
  {
    requirement: "Multiple disaster types / regions",
    status: "planned",
    how: "The one built scenario is a fixed historical replay: Cyclone Titli, Srikakulam district, 11 October 2018, built from real DEM, rainfall, and cyclone-track data. The risk pipeline itself (DEM plus rainfall plus HAND) is not tied to this one storm or bounding box.",
    gap: "There is no UI to load a different disaster or region - it would need a new bounding box and a fresh ingest run, not new code.",
  },
]

function Row({ row }: { row: FeatureRow }) {
  return (
    <div className="border border-ground-300 bg-ground-100 p-4 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-3">
        <span className="font-display font-semibold text-[14px] text-ink-000 leading-snug">{row.requirement}</span>
        <span
          className="shrink-0 font-data text-[11px] uppercase tracking-wide px-2 py-0.5 border"
          style={{ color: STATUS_COLOR[row.status], borderColor: STATUS_COLOR[row.status] }}
        >
          {STATUS_PERCENT[row.status]} · {STATUS_LABEL[row.status]}
        </span>
      </div>
      <p className="text-[13px] text-ink-100 leading-relaxed">{row.how}</p>
      {row.gap && (
        <p className="text-[12px] text-ink-300 leading-relaxed border-t border-ground-300 pt-2 mt-1">
          <span className="font-display uppercase text-[10px] tracking-wide text-ink-300 mr-1">What's missing</span>
          {row.gap}
        </p>
      )}
    </div>
  )
}

export function SolutionSummaryPage() {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-[820px]">
        <h2 className="font-display font-semibold text-[20px] text-ink-000">Solution summary</h2>
        <p className="text-[13px] text-ink-200 mt-1 leading-relaxed">
          What's actually solved, at what percent, and how - checked against the hackathon problem statement
          point by point. Nothing below is claimed without the code behind it.
        </p>

        <div className="mt-5 border border-ground-300 bg-ground-000 p-4">
          <span className="font-display font-semibold text-[13px] text-ink-000">The two problems, kept separate</span>
          <p className="text-[12px] text-ink-200 mt-1 leading-relaxed">
            Q-resQ does two different things. Which areas will flood is a prediction problem, solved with
            supervised machine learning on real terrain and rainfall data. Given a fixed set of rescue units and
            open requests, who goes where is a decision problem under hard constraints, solved as a QUBO. Machine
            learning cannot do the second one - there's no labelled dataset of "optimal rescue decisions," and a
            neural network can't guarantee it never assigns the same boat twice.
          </p>
          <p className="text-[12px] text-ink-200 mt-2 leading-relaxed">
            <span className="font-display uppercase text-[10px] tracking-wide text-ink-300 mr-1">
              On the quantum part
            </span>
            QAOA runs for real - Qiskit Aer, depth 3, warm-started from the greedy solution - and is benchmarked
            head to head against OR-Tools, simulated annealing, and greedy on the same problem instance. At this
            scale it does not beat the classical solvers: parity at best, sometimes a loss, and the benchmark
            table on the dispatch panel shows that honestly, losses included. Quantum is never in the critical
            path - solving always falls back qaoa &rarr; annealing &rarr; greedy, and the last link never fails.
          </p>
        </div>

        <h3 className="font-display font-semibold text-[13px] text-ink-000 uppercase tracking-wide mt-6 mb-2">
          Problem statement, point by point
        </h3>
        <div className="flex flex-col gap-2">
          {REQUIREMENTS.map((row) => (
            <Row key={row.requirement} row={row} />
          ))}
        </div>

        <h3 className="font-display font-semibold text-[13px] text-ink-000 uppercase tracking-wide mt-6 mb-2">
          Raised separately during the build
        </h3>
        <div className="flex flex-col gap-2 mb-6">
          {EXTRA_ROWS.map((row) => (
            <Row key={row.requirement} row={row} />
          ))}
        </div>
      </div>
    </div>
  )
}
