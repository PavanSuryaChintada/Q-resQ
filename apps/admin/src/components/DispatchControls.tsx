import { useState } from "react"
import type { Backend, BenchmarkRow } from "../lib/api"
import { useCreateRequest, useRunBenchmark, useSolveDispatch } from "../lib/hooks"

const BACKENDS: Backend[] = ["greedy", "annealing", "ortools", "qaoa"]

// Aizawl district bbox - see services/api/config.py:REGION["bbox"]
const DEMO_BBOX = { west: 92.55, south: 23.55, east: 93.05, north: 24.05 }
const DEMO_CATEGORIES = ["medical", "stranded", "evacuation"] as const
const DEMO_NOTES = [
  "Family trapped, water rising near the house",
  "Elderly resident unable to evacuate alone",
  "Road cracked, slope moving above the settlement",
  "Group stranded after the ridge road closed",
  "Child injured, needs medical attention",
  "Household cut off, no vehicle access",
]

function randomDemoRequest() {
  const lon = DEMO_BBOX.west + Math.random() * (DEMO_BBOX.east - DEMO_BBOX.west)
  const lat = DEMO_BBOX.south + Math.random() * (DEMO_BBOX.north - DEMO_BBOX.south)
  return {
    id: crypto.randomUUID(),
    location: [lat, lon] as [number, number],
    people_count: 1 + Math.floor(Math.random() * 8),
    category: DEMO_CATEGORIES[Math.floor(Math.random() * DEMO_CATEGORIES.length)],
    note: DEMO_NOTES[Math.floor(Math.random() * DEMO_NOTES.length)],
    created_at: new Date().toISOString(),
  }
}

interface Props {
  showRoutes: boolean
  onToggleRoutes: () => void
}

function GroupLabel({ children }: { children: string }) {
  return (
    <span className="font-display text-[10px] uppercase tracking-[0.1em] text-ink-300 mr-1.5">
      {children}
    </span>
  )
}

export function DispatchControls({ showRoutes, onToggleRoutes }: Props) {
  const [backend, setBackend] = useState<Backend>("greedy")
  const solve = useSolveDispatch()
  const benchmark = useRunBenchmark()
  const createRequest = useCreateRequest()
  const [seeding, setSeeding] = useState(false)
  const [rows, setRows] = useState<BenchmarkRow[] | null>(null)
  const [resultsOpen, setResultsOpen] = useState(true)
  const hasResults = Boolean(solve.data || rows)

  const handleSeedDemoData = async () => {
    setSeeding(true)
    const count = 8
    for (let i = 0; i < count; i++) {
      await createRequest.mutateAsync(randomDemoRequest())
    }
    setSeeding(false)
  }

  return (
    <div className="border-t border-ground-300 bg-ground-100">
      <div className="h-8 flex items-center px-3 bg-ground-200 border-b border-ground-300">
        <span className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200">
          Dispatch
        </span>
      </div>

      <div className="flex items-center flex-wrap gap-x-4 gap-y-2 px-3 py-2">

        <div className="flex items-center">
          <GroupLabel>Map</GroupLabel>
          <button
            onClick={onToggleRoutes}
            className={`h-6 px-2 text-[11px] font-display uppercase tracking-wide border ${
              showRoutes
                ? "bg-ground-300 border-ground-400 text-ink-000"
                : "bg-transparent border-ground-300 text-ink-200 hover:bg-ground-200"
            }`}
          >
            {showRoutes ? "Hide routes" : "Show routes"}
          </button>
        </div>

        <span className="w-px h-5 bg-ground-300" />

        <div className="flex items-center">
          <GroupLabel>Demo</GroupLabel>
          <button
            onClick={handleSeedDemoData}
            disabled={seeding}
            className="h-6 px-2 text-[11px] font-display uppercase tracking-wide border bg-transparent border-ground-300 text-ink-200 hover:bg-ground-200 disabled:opacity-50"
          >
            {seeding ? "Seeding..." : "Seed demo data"}
          </button>
        </div>

        <span className="w-px h-5 bg-ground-300" />

        <div className="flex items-center gap-2">
          <GroupLabel>Solve</GroupLabel>
          <select
            className="bg-ground-300 text-ink-000 text-[12px] font-data h-6 px-1 border border-ground-400"
            value={backend}
            onChange={(e) => setBackend(e.target.value as Backend)}
          >
            {BACKENDS.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
          <button
            onClick={() => solve.mutate({ backend })}
            disabled={solve.isPending}
            className="h-6 px-3 bg-ground-300 border border-ground-400 text-ink-000 text-[11px] font-display uppercase tracking-wide hover:bg-ground-400 disabled:opacity-50"
          >
            {solve.isPending ? "Solving..." : "Dispatch"}
          </button>
          <button
            onClick={() =>
              benchmark.mutate(["greedy", "annealing", "ortools", "qaoa"], { onSuccess: (r) => setRows(r.rows) })
            }
            disabled={benchmark.isPending}
            className="h-6 px-3 bg-transparent border border-ground-300 text-ink-000 text-[11px] font-display uppercase tracking-wide hover:bg-ground-300 disabled:opacity-50"
          >
            {benchmark.isPending ? "Benchmarking..." : "Benchmark (incl. qaoa)"}
          </button>
        </div>

        {hasResults && (
          <button
            onClick={() => setResultsOpen((o) => !o)}
            className="ml-auto h-6 px-2 bg-transparent border border-ground-300 text-ink-300 text-[11px] font-display uppercase tracking-wide hover:bg-ground-200"
          >
            {resultsOpen ? "Hide results ▾" : "Show results ▸"}
          </button>
        )}
      </div>

      {resultsOpen && solve.data && (
        <div className="px-3 py-2 text-[12px] font-data text-ink-100 border-t border-ground-300">
          round {solve.data.id.slice(0, 8)} · {solve.data.assignments.length} assignments ·{" "}
          {solve.data.backend}
          {solve.data.fell_back ? " (fell back)" : ""} · {solve.data.solve_ms}ms
        </div>
      )}

      {resultsOpen && rows && (
        <table className="w-full text-[12px] font-data border-t border-ground-300">
          <thead className="text-ink-200 text-[10px] uppercase font-display bg-ground-200">
            <tr>
              <th className="text-left px-2 py-1 font-normal">Backend</th>
              <th className="text-left px-2 py-1 font-normal">Objective</th>
              <th className="text-left px-2 py-1 font-normal">Solve ms</th>
              <th className="text-left px-2 py-1 font-normal">Valid</th>
              <th className="text-left px-2 py-1 font-normal">Qubits</th>
            </tr>
          </thead>
          <tbody>
            {(() => {
              const best = rows.reduce((a, b) => ((a.objective ?? Infinity) <= (b.objective ?? Infinity) ? a : b))
              return rows.map((row) => (
                <tr
                  key={row.backend}
                  className="border-b border-ground-300/50"
                  style={row === best ? { borderLeft: "2px solid #F0EBE1" } : undefined}
                >
                  <td className="px-2 py-1 text-ink-000">{row.backend}</td>
                  <td className="px-2 py-1 text-ink-100">{row.objective?.toFixed(4)}</td>
                  <td className="px-2 py-1 text-ink-100">{row.solve_ms}</td>
                  <td className="px-2 py-1 text-ink-100">{row.constraints_valid ? "yes" : "no"}</td>
                  <td className="px-2 py-1 text-ink-100">{row.qubit_count ?? "-"}</td>
                </tr>
              ))
            })()}
          </tbody>
        </table>
      )}
    </div>
  )
}
