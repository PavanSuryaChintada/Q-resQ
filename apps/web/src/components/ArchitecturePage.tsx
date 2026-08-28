interface Block {
  title: string
  detail: string
  status: "done" | "partial" | "planned"
}

interface ArchitectureNode {
  id: string
  label: string
  x: number
  y: number
  width: number
  height: number
  category: "frontend" | "backend" | "data" | "optimization" | "ingest"
}

interface ArchitectureConnection {
  from: string
  to: string
  label: string
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

const CATEGORY_COLOR: Record<ArchitectureNode["category"], string> = {
  frontend: "#4A5D52",
  backend: "#C9A227", 
  data: "#D97B1F",
  optimization: "#C23B22",
  ingest: "#7A1E14",
}

const ARCHITECTURE_NODES: ArchitectureNode[] = [
  // Frontend layer
  { id: "web", label: "Web App\n(Vite + React)", x: 50, y: 50, width: 120, height: 60, category: "frontend" },
  { id: "map", label: "MapLibre GL\nRisk Map", x: 200, y: 50, width: 120, height: 60, category: "frontend" },
  
  // Backend layer
  { id: "api", label: "FastAPI\nServices", x: 50, y: 180, width: 120, height: 60, category: "backend" },
  { id: "risk", label: "Risk Service\nTerrain + Rain", x: 200, y: 180, width: 120, height: 60, category: "backend" },
  { id: "dispatch", label: "Dispatch Service\nTriage + Routes", x: 350, y: 180, width: 120, height: 60, category: "backend" },
  
  // Data layer
  { id: "supabase", label: "Supabase\nPostgres + PostGIS", x: 50, y: 310, width: 140, height: 60, category: "data" },
  { id: "realtime", label: "Supabase\nRealtime", x: 220, y: 310, width: 120, height: 60, category: "data" },
  
  // Optimization layer
  { id: "qubo", label: "QUBO Dispatch\nPackage", x: 350, y: 310, width: 120, height: 60, category: "optimization" },
  { id: "qaoa", label: "QAOA\nSolver", x: 500, y: 310, width: 100, height: 60, category: "optimization" },
  { id: "ortools", label: "OR-Tools\nSolver", x: 500, y: 390, width: 100, height: 60, category: "optimization" },
  
  // Ingest layer
  { id: "dem", label: "DEM Ingest\nCopernicus", x: 50, y: 440, width: 120, height: 60, category: "ingest" },
  { id: "rain", label: "Rainfall\nIMD RF25", x: 200, y: 440, width: 120, height: 60, category: "ingest" },
  { id: "osm", label: "OSM\nRoad Network", x: 350, y: 440, width: 120, height: 60, category: "ingest" },
]

const ARCHITECTURE_CONNECTIONS: ArchitectureConnection[] = [
  { from: "web", to: "api", label: "HTTP" },
  { from: "web", to: "map", label: "render" },
  { from: "map", to: "api", label: "GeoJSON" },
  { from: "api", to: "risk", label: "gRPC" },
  { from: "api", to: "dispatch", label: "gRPC" },
  { from: "api", to: "supabase", label: "SQL" },
  { from: "api", to: "realtime", label: "subscribe" },
  { from: "dispatch", to: "qubo", label: "solve()" },
  { from: "qubo", to: "qaoa", label: "fallback" },
  { from: "qubo", to: "ortools", label: "fallback" },
  { from: "risk", to: "dem", label: "load" },
  { from: "risk", to: "rain", label: "load" },
  { from: "dispatch", to: "osm", label: "load" },
  { from: "supabase", to: "realtime", label: "broadcast" },
]

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

function ArchitectureDiagram() {
  return (
    <div className="mt-8 border border-ground-300 bg-ground-000 p-4">
      <h3 className="font-display font-semibold text-[14px] text-ink-000 mb-4">System Architecture Diagram</h3>
      <div className="relative" style={{ height: "520px", width: "100%" }}>
        <svg width="100%" height="100%" viewBox="0 0 650 520">
          {/* Connection lines */}
          {ARCHITECTURE_CONNECTIONS.map((conn, i) => {
            const fromNode = ARCHITECTURE_NODES.find(n => n.id === conn.from)
            const toNode = ARCHITECTURE_NODES.find(n => n.id === conn.to)
            if (!fromNode || !toNode) return null
            
            const fromX = fromNode.x + fromNode.width / 2
            const fromY = fromNode.y + fromNode.height / 2
            const toX = toNode.x + toNode.width / 2
            const toY = toNode.y + toNode.height / 2
            
            return (
              <g key={i}>
                <line
                  x1={fromX}
                  y1={fromY}
                  x2={toX}
                  y2={toY}
                  stroke="#6B6862"
                  strokeWidth="1.5"
                  markerEnd="url(#arrowhead)"
                />
                <text
                  x={(fromX + toX) / 2}
                  y={(fromY + toY) / 2 - 5}
                  fontSize="9"
                  fill="#6B6862"
                  textAnchor="middle"
                  className="font-data"
                >
                  {conn.label}
                </text>
              </g>
            )
          })}
          
          {/* Arrow marker definition */}
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="7"
              refX="9"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 10 3.5, 0 7" fill="#6B6862" />
            </marker>
          </defs>
          
          {/* Nodes */}
          {ARCHITECTURE_NODES.map((node) => (
            <g key={node.id}>
              <rect
                x={node.x}
                y={node.y}
                width={node.width}
                height={node.height}
                fill={CATEGORY_COLOR[node.category]}
                stroke="#101A1E"
                strokeWidth="1"
                rx="2"
              />
              <text
                x={node.x + node.width / 2}
                y={node.y + node.height / 2 - 5}
                fontSize="11"
                fill="#F0EBE1"
                textAnchor="middle"
                className="font-display font-semibold"
              >
                {node.label.split('\n')[0]}
              </text>
              <text
                x={node.x + node.width / 2}
                y={node.y + node.height / 2 + 10}
                fontSize="10"
                fill="#F0EBE1"
                textAnchor="middle"
                className="font-data"
              >
                {node.label.split('\n')[1] || ''}
              </text>
            </g>
          ))}
        </svg>
      </div>
      
      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-4 text-[11px] font-data">
        {Object.entries(CATEGORY_COLOR).map(([category, color]) => (
          <div key={category} className="flex items-center gap-1">
            <span className="w-3 h-3 inline-block" style={{ background: color }} />
            <span className="text-ink-200 capitalize">{category}</span>
          </div>
        ))}
      </div>
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
      
      <ArchitectureDiagram />
    </div>
  )
}
