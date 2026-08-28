import { useState } from "react"
import type { Backend, BenchmarkRow } from "../lib/api"
import { useRunBenchmark, useSeedTitli, useSolveDispatch } from "../lib/hooks"

const BACKENDS: Backend[] = ["greedy", "annealing", "ortools", "qaoa"]

interface Props {
  showRoutes: boolean
  onToggleRoutes: () => void
}

export function DispatchControls({ showRoutes, onToggleRoutes }: Props) {
  const [backend, setBackend] = useState<Backend>("greedy")
  const solve = useSolveDispatch()
  const benchmark = useRunBenchmark()
  const seed = useSeedTitli()
  const [rows, setRows] = useState<BenchmarkRow[] | null>(null)

  return (
    <div className="border-t border-ground-300 bg-ground-100">
      <div className="h-8 flex items-center px-3 bg-ground-200 border-b border-ground-300 gap-2">
        <span className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200">
          Dispatch
        </span>
        <button
          onClick={() => seed.mutate(30)}
          disabled={seed.isPending}
          className="ml-auto h-6 px-2 bg-ground-300 border border-ground-400 text-ink-000 text-[11px] font-display uppercase tracking-wide hover:bg-ground-400 disabled:opacity-50"
        >
          {seed.isPending ? "Seeding..." : "Seed Titli"}
        </button>
        <button
          onClick={() => {
            console.log("Toggle routes clicked, current state:", showRoutes)
            onToggleRoutes()
          }}
          className={`h-6 px-2 text-[11px] font-display uppercase tracking-wide border ${
            showRoutes 
              ? "bg-ground-300 border-ground-400 text-ink-000" 
              : "bg-transparent border-ground-300 text-ink-200 hover:bg-ground-200"
          }`}
        >
          {showRoutes ? "Hide Routes" : "Show Routes"}
        </button>
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

      {solve.data && (
        <div className="px-3 py-2 text-[12px] font-data text-ink-100 border-b border-ground-300">
          round {solve.data.id.slice(0, 8)} · {solve.data.assignments.length} assignments ·{" "}
          {solve.data.backend}
          {solve.data.fell_back ? " (fell back)" : ""} · {solve.data.solve_ms}ms
        </div>
      )}

      {rows && (
        <table className="w-full text-[12px] font-data">
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
