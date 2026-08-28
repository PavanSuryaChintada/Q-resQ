import { useState } from "react"
import { useCreateRequest, useRequests } from "../lib/hooks"

const SEV_BAND_COLOR = ["#4A5D52", "#C9A227", "#D97B1F", "#C23B22", "#7A1E14"]

function bandForSeverity(sev: number | null | undefined): number {
  const s = sev ?? 0
  if (s < 0.2) return 0
  if (s < 0.4) return 1
  if (s < 0.6) return 2
  if (s < 0.8) return 3
  return 4
}

export function RequestsPanel({ center }: { center: [number, number] }) {
  const { data: requests } = useRequests()
  const createRequest = useCreateRequest()
  const [people, setPeople] = useState(2)
  const [category, setCategory] = useState<"medical" | "stranded" | "evacuation">("stranded")
  const [note, setNote] = useState("")

  const sorted = [...(requests ?? [])].sort((a, b) => (b.severity ?? 0) - (a.severity ?? 0))

  function submit() {
    const jitterLat = center[0] + (Math.random() - 0.5) * 0.02
    const jitterLon = center[1] + (Math.random() - 0.5) * 0.02
    createRequest.mutate({
      id: crypto.randomUUID(),
      location: [jitterLat, jitterLon],
      people_count: people,
      category,
      note: note || undefined,
      created_at: new Date().toISOString(),
    })
    setNote("")
  }

  return (
    <div className="flex-1 flex flex-col border-t border-ground-300 min-h-0">
      <div className="h-8 flex items-center justify-between px-3 bg-ground-200 border-b border-ground-300">
        <span className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200">
          Request queue
        </span>
        <div className="flex items-center gap-2">
          <select
            className="bg-ground-300 text-ink-000 text-[12px] font-body h-6 px-1 border border-ground-400"
            value={category}
            onChange={(e) => setCategory(e.target.value as typeof category)}
          >
            <option value="medical">Medical</option>
            <option value="stranded">Stranded</option>
            <option value="evacuation">Evacuation</option>
          </select>
          <input
            type="number"
            min={1}
            className="w-12 bg-ground-300 text-ink-000 font-data text-[12px] h-6 px-1 border border-ground-400"
            value={people}
            onChange={(e) => setPeople(Number(e.target.value))}
          />
          <input
            type="text"
            placeholder="note"
            className="w-32 bg-ground-300 text-ink-000 text-[12px] font-body h-6 px-1 border border-ground-400"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <button
            onClick={submit}
            disabled={createRequest.isPending}
            className="h-6 px-3 bg-ground-300 border border-ground-400 text-ink-000 text-[11px] font-display uppercase tracking-wide hover:bg-ground-400 disabled:opacity-50"
          >
            {createRequest.isPending ? "Queuing..." : "Submit"}
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-[13px] font-body">
          <thead className="sticky top-0 bg-ground-200 text-ink-200 text-[11px] uppercase font-display">
            <tr>
              <th className="text-left px-2 py-1 font-normal">Sev</th>
              <th className="text-left px-2 py-1 font-normal">People</th>
              <th className="text-left px-2 py-1 font-normal">Category</th>
              <th className="text-left px-2 py-1 font-normal">Status</th>
              <th className="text-left px-2 py-1 font-normal">Note</th>
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 && (
              <tr>
                <td colSpan={5} className="px-2 py-4 text-ink-300 text-center">
                  No open requests. Requests appear here as they arrive.
                </td>
              </tr>
            )}
            {sorted.map((r) => {
              const band = bandForSeverity(r.severity)
              return (
                <tr key={r.id} className="border-b border-ground-300" style={{ borderLeft: `2px solid ${SEV_BAND_COLOR[band]}` }}>
                  <td className="px-2 py-1 font-data">{(r.severity ?? 0).toFixed(2)}</td>
                  <td className="px-2 py-1 font-data">{r.people_count}</td>
                  <td className="px-2 py-1">{r.category}</td>
                  <td className="px-2 py-1 text-ink-200">{r.status}</td>
                  <td className="px-2 py-1 text-ink-200">{r.note ?? ""}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
