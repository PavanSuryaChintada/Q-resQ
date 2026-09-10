// In dev, "/api" is rewritten to the local backend by vite.config.ts's
// proxy. In production there's no dev-server proxy, so VITE_API_URL
// must be set at build time to the deployed backend's full URL.
const BASE = import.meta.env.VITE_API_URL || "/api"

export type Backend = "qaoa" | "annealing" | "ortools" | "greedy" | "manual"

export interface RiskCellProperties {
  id: number
  hand_m?: number | null
  slope_deg?: number | null
  dist_stream_m?: number | null
  risk_score?: number | null
  risk_band?: number | null
}

export interface RiskCellFeature {
  type: "Feature"
  geometry: { type: "Point" | "Polygon"; coordinates: number[] }
  properties: RiskCellProperties
}

export interface RiskCellCollection {
  type: "FeatureCollection"
  features: RiskCellFeature[]
}

export interface FeatureContribution {
  name: string
  value: number
  contribution: number
}

export interface RiskCellDetail {
  id: number
  risk_score: number
  risk_band: number
  top_features: FeatureContribution[]
}

export interface RequestOut {
  id: string
  location: [number, number]
  people_count: number
  category: "medical" | "stranded" | "evacuation"
  note?: string | null
  created_at: string
  status: "open" | "assigned" | "in_progress" | "resolved" | "cancelled"
  severity?: number | null
  sev_people?: number | null
  sev_category?: number | null
  sev_area_risk?: number | null
  sev_wait?: number | null
  sev_isolation?: number | null
}

export interface ReportOut {
  id: string
  location: [number, number]
  kind: "crack" | "slope_movement" | "road_blocked" | "water_seepage" | "other"
  note: string | null
  media_url: string | null
  media_type: "image" | "video" | null
  status: "pending" | "verified" | "dismissed" | "duplicate"
  created_at: string
  reporter_hash: string
}

export interface UnitOut {
  id: string
  label: string
  kind: "boat" | "ambulance" | "truck" | "team"
  capacity: number
  position: [number, number]
  status: "available" | "assigned" | "en_route" | "returning" | "offline"
  updated_at: string
}

export interface AssignmentOut {
  id: string
  unit_id: string
  request_id: string
  zone_id?: number | null
  travel_s?: number | null
  route?: { type: "LineString"; coordinates: number[][] } | null
  route_source?: "road" | "direct" | null
}

export interface DispatchRoundOut {
  id: string
  started_at: string
  zone_count?: number | null
  request_count?: number | null
  unit_count?: number | null
  backend?: Backend | null
  fell_back: boolean
  objective?: number | null
  solve_ms?: number | null
  assignments: AssignmentOut[]
}

export interface BenchmarkRow {
  backend: string
  objective?: number | null
  solve_ms?: number | null
  constraints_valid?: boolean | null
  qubit_count?: number | null
  notes?: string | null
}

export interface BenchmarkRunResult {
  round_id: string
  rows: BenchmarkRow[]
}

export interface LogLine {
  id: number
  at: string
  channel: "risk" | "intake" | "dispatch" | "road" | "system"
  severity: number
  message: string
}

export interface SettlementIsolationOut {
  id: number
  name: string
  population: number | null
  isolated: boolean
  isolation_score: number
  component_size: number
  path_to_hq: boolean
  lon: number | null
  lat: number | null
}

export interface DemoTriggerOut {
  way_id: string
  ref: string
  isolated_settlements: string[]
  backup_way_id: string | null
}

export interface RoadGeometry {
  type: "LineString"
  coordinates: [number, number][]
}

export interface AlertOut {
  id: string
  cap_xml: string
  severity: number
  headline: string
  description: string
  trigger_src: string
  languages: string[]
  issued_at: string
  expires_at: string
}

export interface RoadBlockResult {
  way_id: string
  segment_id: number
  blocked: boolean
  isolated_settlements: string[]
  geom: RoadGeometry | null
  message: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!response.ok) {
    const body = await response.text()
    let detail = body
    try {
      const parsed = JSON.parse(body)
      if (typeof parsed?.detail === "string") detail = parsed.detail
    } catch {
      // not JSON - fall back to raw body text
    }
    throw new Error(detail)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  riskCells: () => request<RiskCellCollection>("/risk/cells"),
  riskCell: (id: number) => request<RiskCellDetail>(`/risk/cell/${id}`),

  requests: (status?: string) =>
    request<RequestOut[]>(`/requests${status ? `?status=${status}` : ""}`),
  createRequest: (payload: {
    id: string
    location: [number, number]
    people_count: number
    category: "medical" | "stranded" | "evacuation"
    note?: string
    created_at: string
  }) => request<RequestOut>("/requests", { method: "POST", body: JSON.stringify(payload) }),

  reports: (status?: string) =>
    request<ReportOut[]>(`/reports${status ? `?status=${status}` : ""}`),
  updateReport: (id: string, status: string) =>
    request<ReportOut>(`/reports/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),

  units: () => request<UnitOut[]>("/units"),

  assignments: () => request<AssignmentOut[]>("/dispatch/assignments"),

  solveDispatch: (backend: Backend, timeout_s = 10.0) =>
    request<DispatchRoundOut>("/dispatch/solve", {
      method: "POST",
      body: JSON.stringify({ backend, timeout_s }),
    }),

  assignUnit: (requestId: string, unitId: string) =>
    request<AssignmentOut>("/dispatch/assign", {
      method: "POST",
      body: JSON.stringify({ request_id: requestId, unit_id: unitId }),
    }),

  runBenchmark: (backends?: Backend[]) =>
    request<BenchmarkRunResult>("/benchmark/run", {
      method: "POST",
      body: JSON.stringify({ backends: backends ?? null }),
    }),

  log: (since?: number) => request<LogLine[]>(`/log${since ? `?since=${since}` : ""}`),

  isolation: () => request<SettlementIsolationOut[]>("/roads/isolation"),
  demoTrigger: () => request<DemoTriggerOut>("/roads/demo/trigger"),
  blockDemoTrigger: () => request<RoadBlockResult>("/roads/demo/block", { method: "POST" }),
  clearRoadSegment: (segmentId: number) =>
    request<{ segment_id: number; blocked: boolean }>("/roads/clear", {
      method: "POST",
      body: JSON.stringify({ segment_id: segmentId }),
    }),

  createAlert: (payload: {
    severity: number
    headline: string
    area_name: string
    trigger_src: "risk_band" | "deformation" | "report" | "manual"
    language?: string
  }) => request<AlertOut>("/alerts/", { method: "POST", body: JSON.stringify(payload) }),
}
