interface Block {
  title: string
  detail: string
  status: "done" | "partial" | "planned"
}

const STATUS_COLOR: Record<Block["status"], string> = {
  done: "#5C8A6E",
  partial: "#C9A227",
  planned: "#6B6862",
}
const STATUS_LABEL: Record<Block["status"], string> = {
  done: "built + verified",
  partial: "built, partially wired",
  planned: "not built yet",
}

function Card({ block }: { block: Block }) {
  return (
    <div className="border border-ground-300 bg-ground-100 p-3 flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <span className="w-2 h-2 shrink-0" style={{ background: STATUS_COLOR[block.status] }} />
        <span className="font-display font-semibold text-[13px] text-ink-000">{block.title}</span>
      </div>
      <p className="text-[12px] text-ink-200 leading-snug">{block.detail}</p>
      <span className="font-data text-[10px] text-ink-300 uppercase mt-1">{STATUS_LABEL[block.status]}</span>
    </div>
  )
}

const ROWS: Block[][] = [
  [
    {
      title: "apps/web",
      detail: "Vite + React + TypeScript + Tailwind + MapLibre GL + TanStack Query. This page.",
      status: "partial",
    },
  ],
  [
    {
      title: "services/api routers",
      detail: "FastAPI: risk, requests, units, dispatch, benchmark, log, seed. Requests/units are in-memory stores, not yet wired to Supabase.",
      status: "partial",
    },
  ],
  [
    {
      title: "risk/terrain.py",
      detail: "DEM -> HAND, slope, TWI, distance-to-stream via pysheds. Runs on the real Srikakulam Copernicus DEM.",
      status: "done",
    },
    {
      title: "risk/heuristic.py",
      detail: "Weighted physical risk formula (HAND 40% + rain 30% + slope 15% + dist-stream 10% + drainage 5%). No trained model yet.",
      status: "done",
    },
    {
      title: "risk/rainfall.py",
      detail: "rain_72h from the real IMD RF25 gridded rainfall NetCDF, not a fixture - verified against the actual Titli rainfall spike.",
      status: "done",
    },
    {
      title: "dispatch/severity.py",
      detail: "Triage: people + category + area_risk (from risk/features.py) + wait time, all relative to the current queue.",
      status: "done",
    },
  ],
  [
    {
      title: "packages/qubo-dispatch",
      detail: "Standalone QUBO library. greedy / annealing / ortools / qaoa solvers, fallback router, geographic partitioning, benchmarking.",
      status: "done",
    },
  ],
  [
    {
      title: "ingest/ scripts",
      detail: "DEM (Planetary Computer + OpenTopography), cyclone track (IBTrACS), rainfall (Open-Meteo + NASA POWER + IMD RF25). OSM and SAR fetch real data but hit resource limits on this machine mid-download.",
      status: "partial",
    },
  ],
  [
    {
      title: "risk/model.py (LightGBM)",
      detail: "Trained model on SAR flood labels, per docs/TRD.md #3. Not built - the heuristic is the only risk path right now.",
      status: "planned",
    },
    {
      title: "roads/graph.py",
      detail: "Flood-aware road network via osmnx. Not built - dispatch currently uses straight-line (haversine) distance as a placeholder for travel time.",
      status: "planned",
    },
    {
      title: "Offline / PWA",
      detail: "Service worker, IndexedDB queue, background sync. Cut for this session's time budget - see docs/TRD.md #7.",
      status: "planned",
    },
  ],
  [
    {
      title: "Supabase (Postgres + PostGIS)",
      detail: "Schema applied and live (8 tables, RLS, extensions verified). App routers don't read/write it yet - still in-memory.",
      status: "partial",
    },
  ],
]

export function ArchitecturePage() {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <h1 className="font-display font-semibold text-[18px] text-ink-000 mb-1">System architecture</h1>
      <p className="text-[13px] text-ink-200 mb-6 max-w-2xl">
        What's actually built and wired, top to bottom. Colour marks real status, not aspiration - amber
        pieces work but aren't fully connected, grey pieces don't exist yet.
      </p>
      <div className="flex flex-col gap-3 max-w-4xl">
        {ROWS.map((row, i) => (
          <div key={i} className="grid gap-3" style={{ gridTemplateColumns: `repeat(${row.length}, 1fr)` }}>
            {row.map((block) => (
              <Card key={block.title} block={block} />
            ))}
          </div>
        ))}
      </div>
      <div className="mt-6 flex gap-4 text-[11px] font-data text-ink-200">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 inline-block" style={{ background: STATUS_COLOR.done }} /> done
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 inline-block" style={{ background: STATUS_COLOR.partial }} /> partial
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 inline-block" style={{ background: STATUS_COLOR.planned }} /> planned
        </span>
      </div>
    </div>
  )
}
