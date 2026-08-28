const BASE = "/api"

export type Backend = "qaoa" | "annealing" | "ortools" | "greedy"

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

export interface SeedResult {
  status: "seeded"
  units_created: number
  requests_created: number
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`${init?.method ?? "GET"} ${path} -> ${response.status}: ${body}`)
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

  units: () => request<UnitOut[]>("/units"),

  solveDispatch: (backend: Backend, timeout_s = 10.0) =>
    request<DispatchRoundOut>("/dispatch/solve", {
      method: "POST",
      body: JSON.stringify({ backend, timeout_s }),
    }),

  runBenchmark: (backends?: Backend[]) =>
    request<BenchmarkRunResult>("/benchmark/run", {
      method: "POST",
      body: JSON.stringify({ backends: backends ?? null }),
    }),

  log: (since?: number) => request<LogLine[]>(`/log${since ? `?since=${since}` : ""}`),

  seedTitli: (n_requests = 30) =>
    request<SeedResult>(`/seed/titli?n_requests=${n_requests}`, { method: "POST" }),
}
