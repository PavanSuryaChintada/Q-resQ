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
  status: Block["status"]
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

// Grid: columns 180px apart, rows 130px apart, nodes 150x64 - wide gaps
// so edge labels never sit on top of a node or another line.
const COL = (n: number) => 40 + n * 180
const ROW = (n: number) => 40 + n * 130
const NODE_W = 150
const NODE_H = 64

const ARCHITECTURE_NODES: ArchitectureNode[] = [
  // Row 0: frontend
  { id: "web", label: "Web App\nVite + React", x: COL(0), y: ROW(0), width: NODE_W, height: NODE_H, category: "frontend", status: "partial" },
  { id: "map", label: "MapLibre GL\nRisk Map", x: COL(1), y: ROW(0), width: NODE_W, height: NODE_H, category: "frontend", status: "partial" },
  { id: "citizen", label: "Citizen PWA\nReports + SOS", x: COL(2), y: ROW(0), width: NODE_W, height: NODE_H, category: "frontend", status: "done" },

  // Row 1: backend services
  { id: "api", label: "FastAPI\nRouters", x: COL(0), y: ROW(1), width: NODE_W, height: NODE_H, category: "backend", status: "partial" },
  { id: "risk", label: "Risk\nSusceptibility", x: COL(1), y: ROW(1), width: NODE_W, height: NODE_H, category: "backend", status: "done" },
  { id: "insar", label: "InSAR\nDeformation", x: COL(2), y: ROW(1), width: NODE_W, height: NODE_H, category: "backend", status: "done" },
  { id: "roads", label: "Roads\nIsolation", x: COL(3), y: ROW(1), width: NODE_W, height: NODE_H, category: "backend", status: "done" },
  { id: "dispatch", label: "Dispatch\nTriage + Routes", x: COL(4), y: ROW(1), width: NODE_W, height: NODE_H, category: "backend", status: "done" },

  // Row 2: data + optimization
  { id: "reports_alerts", label: "Reports +\nAlerts (CAP)", x: COL(0), y: ROW(2), width: NODE_W, height: NODE_H, category: "backend", status: "done" },
  { id: "supabase", label: "Supabase\nPostgres + PostGIS", x: COL(1), y: ROW(2), width: NODE_W, height: NODE_H, category: "data", status: "done" },
  { id: "realtime", label: "Supabase\nRealtime", x: COL(2), y: ROW(2), width: NODE_W, height: NODE_H, category: "data", status: "planned" },
  { id: "qubo", label: "QUBO Dispatch\nPackage", x: COL(3), y: ROW(2), width: NODE_W, height: NODE_H, category: "optimization", status: "done" },

  // Row 3: ingest
  { id: "dem", label: "DEM Ingest\nCopernicus", x: COL(0), y: ROW(3), width: NODE_W, height: NODE_H, category: "ingest", status: "done" },
  { id: "insar_data", label: "InSAR Data\nSentinel-1 (synthetic)", x: COL(1), y: ROW(3), width: NODE_W, height: NODE_H, category: "ingest", status: "partial" },
  { id: "osm", label: "OSM\nRoad Network", x: COL(2), y: ROW(3), width: NODE_W, height: NODE_H, category: "ingest", status: "done" },
  { id: "rain", label: "Rainfall\nSMAP + ERA5 (synthetic)", x: COL(3), y: ROW(3), width: NODE_W, height: NODE_H, category: "ingest", status: "partial" },
]

const ARCHITECTURE_CONNECTIONS: ArchitectureConnection[] = [
  { from: "web", to: "api", label: "HTTP" },
  { from: "web", to: "map", label: "render" },
  { from: "citizen", to: "api", label: "HTTP" },
  { from: "map", to: "api", label: "GeoJSON" },
  { from: "api", to: "risk", label: "call" },
  { from: "api", to: "insar", label: "call" },
  { from: "api", to: "roads", label: "call" },
  { from: "api", to: "dispatch", label: "call" },
  { from: "api", to: "reports_alerts", label: "call" },
  { from: "api", to: "supabase", label: "SQL" },
  { from: "api", to: "realtime", label: "subscribe" },
  { from: "dispatch", to: "qubo", label: "solve()" },
  { from: "dispatch", to: "roads", label: "isolation" },
  { from: "risk", to: "dem", label: "load" },
  { from: "insar", to: "insar_data", label: "load" },
  { from: "roads", to: "osm", label: "load" },
  { from: "risk", to: "rain", label: "load" },
  { from: "supabase", to: "realtime", label: "broadcast" },
  { from: "reports_alerts", to: "supabase", label: "SQL" },
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

const DIAGRAM_W = COL(4) + NODE_W + 40
const DIAGRAM_H = ROW(3) + NODE_H + 40

function ArchitectureDiagram() {
  return (
    <div className="mt-8 border border-ground-300 bg-ground-000 p-4">
      <h3 className="font-display font-semibold text-[14px] text-ink-000 mb-1">System architecture diagram</h3>
      <p className="text-[11px] text-ink-300 mb-4">
        Node border colour is build status (see legend below) - the same status this whole page reports, not decoration.
      </p>
      <div className="relative w-full overflow-x-auto">
        <svg width="100%" height={DIAGRAM_H} viewBox={`0 0 ${DIAGRAM_W} ${DIAGRAM_H}`} style={{ minWidth: 820 }}>
          <defs>
            <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#6B6862" />
            </marker>
          </defs>

          {/* Connection lines, drawn first so nodes sit on top */}
          {ARCHITECTURE_CONNECTIONS.map((conn, i) => {
            const fromNode = ARCHITECTURE_NODES.find((n) => n.id === conn.from)
            const toNode = ARCHITECTURE_NODES.find((n) => n.id === conn.to)
            if (!fromNode || !toNode) return null

            const fromCx = fromNode.x + fromNode.width / 2
            const fromCy = fromNode.y + fromNode.height / 2
            const toCx = toNode.x + toNode.width / 2
            const toCy = toNode.y + toNode.height / 2

            // Clip the line to each box's edge (not its centre) so arrows
            // land on the border, and route from the nearer face when
            // nodes are stacked vertically vs. side by side.
            const dx = toCx - fromCx
            const dy = toCy - fromCy
            const vertical = Math.abs(dy) > Math.abs(dx)
            const fromX = vertical ? fromCx : fromCx + Math.sign(dx) * (fromNode.width / 2)
            const fromY = vertical ? fromCy + Math.sign(dy) * (fromNode.height / 2) : fromCy
            const toX = vertical ? toCx : toCx - Math.sign(dx) * (toNode.width / 2)
            const toY = vertical ? toCy - Math.sign(dy) * (toNode.height / 2) : toCy
            const midX = (fromX + toX) / 2
            const midY = (fromY + toY) / 2
            const labelW = conn.label.length * 5.2 + 8

            return (
              <g key={i}>
                <line x1={fromX} y1={fromY} x2={toX} y2={toY} stroke="#6B6862" strokeWidth="1.25" markerEnd="url(#arrowhead)" />
                <rect x={midX - labelW / 2} y={midY - 8} width={labelW} height={13} fill="#101A1E" />
                <text x={midX} y={midY + 2} fontSize="9" fill="#9A968D" textAnchor="middle" className="font-data">
                  {conn.label}
                </text>
              </g>
            )
          })}

          {/* Nodes */}
          {ARCHITECTURE_NODES.map((node) => (
            <g key={node.id}>
              <rect
                x={node.x}
                y={node.y}
                width={node.width}
                height={node.height}
                fill={CATEGORY_COLOR[node.category]}
                stroke={STATUS_COLOR[node.status]}
                strokeWidth="2"
                rx="2"
              />
              <text x={node.x + node.width / 2} y={node.y + node.height / 2 - 6} fontSize="12" fill="#F0EBE1" textAnchor="middle" className="font-display font-semibold">
                {node.label.split('\n')[0]}
              </text>
              <text x={node.x + node.width / 2} y={node.y + node.height / 2 + 11} fontSize="10" fill="#F0EBE1" textAnchor="middle" className="font-data">
                {node.label.split('\n')[1] || ''}
              </text>
            </g>
          ))}
        </svg>
      </div>

      <div className="mt-4 flex flex-wrap gap-4 text-[11px] font-data">
        <span className="text-ink-300">Fill = layer</span>
        {Object.entries(CATEGORY_COLOR).map(([category, color]) => (
          <div key={category} className="flex items-center gap-1">
            <span className="w-3 h-3 inline-block" style={{ background: color }} />
            <span className="text-ink-200 capitalize">{category}</span>
          </div>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-4 text-[11px] font-data">
        <span className="text-ink-300">Border = status</span>
        {(Object.entries(STATUS_COLOR) as [Block["status"], string][]).map(([status, color]) => (
          <div key={status} className="flex items-center gap-1">
            <span className="w-3 h-3 inline-block border-2" style={{ borderColor: color, background: "transparent" }} />
            <span className="text-ink-200 capitalize">{status}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

const ROWS: Block[][] = [
  [
    {
      title: "apps/admin",
      detail: "Vite + React + TypeScript + Tailwind + MapLibre GL. Risk map, dispatch, road/isolation search and blocking, citizen report review with photos, alert triggering - all against the real API, not fixtures.",
      status: "partial",
    },
  ],
  [
    {
      title: "services/api routers",
      detail: "FastAPI: risk, requests, units, dispatch, benchmark, log, roads, reports, alerts, insar, resources. All wired to Supabase and exercised end to end, not just present.",
      status: "partial",
    },
  ],
  [
    {
      title: "risk/terrain.py",
      detail: "DEM -> slope, aspect (sin/cos), curvature, LS, HAND, TWI, distance to stream. Copernicus DEM 30 m -> 100 m grid.",
      status: "done",
    },
    {
      title: "risk/heuristic.py",
      detail: "Landslide susceptibility index: slope + profile curvature + cut-slope proximity + forest cover + LS factor. Physical index, no trained model yet.",
      status: "done",
    },
    {
      title: "risk/features.py",
      detail: "Terrain features sampled from pre-computed rasters, provenance-labelled \"index\" for all cells. Disk-cached, 284,070 cells.",
      status: "done",
    },
    {
      title: "dispatch/severity.py",
      detail: "Triage: 0.28 people + 0.28 category + 0.22 area_risk + 0.12 wait + 0.10 isolation. Isolation term is wired and verified: an isolated settlement's request outranks an identical non-isolated one.",
      status: "done",
    },
  ],
  [
    {
      title: "insar/",
      detail: "Deformation time series API, classified stable/creeping/accelerating. Sentinel-1 SLC never arrived in the build window, so this serves labelled SYNTHETIC - ILLUSTRATIVE ONLY data, not measured. The SBAS processing pipeline is real; only the input scene is not.",
      status: "done",
    },
  ],
  [
    {
      title: "roads/isolation.py",
      detail: "Real OSM graph (4,629 segments, 52 settlements), blockage-aware, connected components recomputed live. Block/clear endpoints, plus search-by-settlement and report-driven blocking - not limited to one hardcoded road.",
      status: "done",
    },
  ],
  [
    {
      title: "reports/",
      detail: "Citizen PWA submissions with photo attachments, offline queueing, location + time clustering. Reports render with photo thumbnails in the admin queue and can be approved into a real dispatch request.",
      status: "done",
    },
  ],
  [
    {
      title: "alerts/",
      detail: "Real CAP 1.2 XML generation, verified end to end. Geo-fenced evaluation is client-side ready. No SMS gateway integration - needs credentials and procurement, not engineering.",
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
      detail: "DEM, terrain, rainfall, landcover, roads/facilities/waterways/settlements, landslide catalogue. All run.",
      status: "done",
    },
  ],
  [
    {
      title: "risk/model.py (LightGBM)",
      detail: "Training pipeline built and tested. 58 positive samples below the 150 threshold for spatial cross-validation. Needs GSI inventory data, not code.",
      status: "planned",
    },
  ],
  [
    {
      title: "Supabase (Postgres + PostGIS)",
      detail: "Schema applied and live across every table used above - roads, settlements, reports, alerts, requests, units, dispatch log. RLS policies and a live schema audit (several tables had drifted from schema.sql or had no access policy at all) were both real bugs found and fixed this build.",
      status: "done",
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
