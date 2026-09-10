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
    requirement: "Landslide susceptibility assessment",
    status: "done",
    how: "Physical index over slope, profile curvature, cut-slope proximity, forest cover and LS factor, computed from real Copernicus DEM terrain derivatives and OSM road network. 284,070 cells at 100 m over Aizawl district. Every cell is provenance-labelled \"index\" — the training pipeline is built but needs more landslide inventory data to train a model that survives spatial cross-validation.",
    gap: "The index uses district-median profile curvature for perfectly flat cells (46 cells) where the derivative is genuinely undefined — disclosed in the log, not fabricated. Lithology weight is renormalised across the other five factors when GSI data is unavailable, rather than left as a depressed score.",
  },
  {
    requirement: "Deformation monitoring (InSAR)",
    status: "partial",
    how: "Sentinel-1 SBAS interferometry pipeline built and documented. For the demo, a pre-computed deformation time series for one corridor in Aizawl is served through a live-looking API. Points are classified as stable, creeping, or accelerating based on velocity and acceleration thresholds.",
    gap: "Deformation is pre-computed, not live. Live SBAS processing takes days of compute. The pipeline exists; live processing is a compute-scheduling problem, not an algorithmic one. Points outside the processed corridor are empty — we do not interpolate across ground we did not measure.",
  },
  {
    requirement: "Road isolation analysis",
    status: "done",
    how: "Real OSM road network (4,629 segments, 52 settlements) as a connected-component graph. Blocking a segment recomputes components live and marks every settlement's isolation score, component size, and whether a path to district HQ survives. Isolation is not just displayed — it is wired into dispatch severity as its own weighted term, verified: an otherwise-identical request near an isolated settlement outranks one that isn't. Blocking is not limited to one hardcoded road — any of the 52 settlements can be searched and its nearest real road blocked or cleared, and approving a citizen's road-blocked report finds and blocks the real nearest segment automatically.",
    gap: "Realtime broadcast (push updates to connected clients on block/clear) is not wired — the admin map polls instead.",
  },
  {
    requirement: "Interactive map showing vulnerable locations",
    status: "done",
    how: "MapLibre GL map with risk cells coloured by severity band, click-to-inspect detail panel per cell, live request and unit markers, and dispatch routes drawn between them.",
  },
  {
    requirement: "Dashboard for administrators / rescue teams",
    status: "done",
    how: "Full operations dashboard: layers panel, risk-cell detail, units panel, request queue with search and a card-carousel view, dispatch controls with a live solver benchmark, and the dispatch ledger.",
  },
  {
    requirement: "Prioritisation of rescue requests based on severity",
    status: "done",
    how: "Each request's severity is computed from people count, category, area risk, wait time, and isolation. The dispatch solver optimises severity times people count against travel time under hard capacity constraints — it never double-books a unit or a request. The request queue is sorted by severity and searchable.",
  },
  {
    requirement: "Citizen reporting and clustering",
    status: "done",
    how: "Citizen PWA: emergency SOS, photo reports (camera or gallery) with location, offline queueing via IndexedDB, editable profile. Reports land in the same backend the admin dashboard reads, photo thumbnails included, and cluster by location and time so ten photos of one slope arrive as one incident, not ten rows.",
    gap: "On-device photo classification is not built — photos are attached and reviewed by an officer, not auto-classified. Camera capture depends on the browser's secure-context rules; over plain HTTP on a phone it may fall back to a file picker instead of opening the camera directly.",
  },
  {
    requirement: "CAP alert generation",
    status: "done",
    how: "Common Alerting Protocol XML generated on demand — real CAP 1.2 payloads with identifier, severity, headline, and description, verified end to end. Geo-fenced evaluation is client-side ready for offline capability.",
    gap: "SMS/broadcast gateway integration needs credentials and procurement, not engineering — the payload itself is standards-compliant today.",
  },
]

const EXTRA_ROWS: FeatureRow[] = [
  {
    requirement: "Soil moisture integration",
    status: "partial",
    how: "Satellite-derived soil moisture from SMAP and ERA5-Land, integrated into the trigger index alongside rainfall accumulation at 1, 3, 7 and 15 days.",
    gap: "No in-situ sensors. The sensor ingest contract is documented and the table exists, but we did not simulate hardware we do not have.",
  },
  {
    requirement: "Quantum response allocation",
    status: "done",
    how: "Response allocation is formulated as a QUBO and runs on classical solvers (OR-Tools, simulated annealing, greedy) today. The formulation is hardware-ready for quantum backends.",
    gap: "Quantum is not in the critical path — the system runs with the quantum toolchain uninstalled. We never claim quantum advantage.",
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
        <h2 className="font-display font-semibold text-[20px] text-ink-000">Landslide early warning for the North Eastern Region</h2>
        <p className="text-[13px] text-ink-200 mt-1 leading-relaxed">
          Aizawl district, Mizoram · 284,070 cells at 100 m
        </p>

        <div className="mt-5 border border-ground-300 bg-ground-000 p-4">
          <span className="font-display font-semibold text-[13px] text-ink-000">The three claims</span>
          <p className="text-[12px] text-ink-200 mt-2 leading-relaxed">
            <span className="font-display uppercase text-[10px] tracking-wide text-ink-300 mr-1">Measured, not only inferred.</span>
            Susceptibility tells you which slopes could fail. Sentinel-1 interferometry tells you which slope is failing. Steady creep is normal on a hillslope; acceleration is not. Acceleration is the warning signal.
          </p>
          <p className="text-[12px] text-ink-200 mt-2 leading-relaxed">
            <span className="font-display uppercase text-[10px] tracking-wide text-ink-300 mr-1">Isolation is its own axis of urgency.</span>
            In a flood, people self-evacuate. On a ridge, one blocked road removes every route out. A settlement of forty with no path to the district headquarters can legitimately outrank a larger one that still has a road. Isolation enters the priority score as its own term, not as a proxy for hazard exposure.
          </p>
          <p className="text-[12px] text-ink-200 mt-2 leading-relaxed">
            <span className="font-display uppercase text-[10px] tracking-wide text-ink-300 mr-1">We show you where we do not know.</span>
            Every cell is labelled with its provenance — learned model or physical index. Deformation renders only inside the processed corridor; outside it the layer is empty and says so. We do not interpolate across ground we did not measure.
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
