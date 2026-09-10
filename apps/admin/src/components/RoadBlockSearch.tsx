import { useState } from "react"
import type { NearestSegmentOut, SettlementIsolationOut } from "../lib/api"
import { useBlockedSegments, useBlockSegment, useClearRoadSegment, useNearestSegment } from "../lib/hooks"

interface Props {
  settlements: SettlementIsolationOut[]
}

// Not just NH6 - any road can be blocked: search a settlement (or type
// coordinates), find the real nearest road segment, and block it. The
// same backend endpoint the NH6 demo trigger uses, generalised.
export function RoadBlockSearch({ settlements }: Props) {
  const [query, setQuery] = useState("")
  const [preview, setPreview] = useState<NearestSegmentOut | null>(null)
  const nearestSegment = useNearestSegment()
  const blockSegment = useBlockSegment()
  const clearRoadSegment = useClearRoadSegment()
  const { data: blocked } = useBlockedSegments()

  const matches = query.trim()
    ? settlements.filter((s) => s.name.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 6)
    : []

  const handleSelectSettlement = async (s: SettlementIsolationOut) => {
    setQuery(s.name)
    if (s.lat == null || s.lon == null) return
    const result = await nearestSegment.mutateAsync({ lat: s.lat, lon: s.lon })
    setPreview(result)
  }

  const handleBlock = async () => {
    if (!preview) return
    await blockSegment.mutateAsync({ segmentId: preview.id, reason: "confirmed" })
    setPreview(null)
    setQuery("")
  }

  return (
    <div className="border-t border-ground-300 p-3">
      <div className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200 mb-2">
        Custom road block
      </div>
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setPreview(null)
          }}
          placeholder="Search a settlement..."
          className="w-full px-2 py-1.5 bg-ground-000 border border-ground-300 text-ink-000 text-[12px] focus:outline-none focus:border-ink-000"
        />
        {matches.length > 0 && !preview && (
          <div className="absolute z-10 left-0 right-0 mt-0.5 bg-ground-100 border border-ground-400 max-h-40 overflow-y-auto">
            {matches.map((s) => (
              <button
                key={s.id}
                onClick={() => handleSelectSettlement(s)}
                className="w-full text-left px-2 py-1.5 text-[12px] text-ink-000 hover:bg-ground-200 flex items-center justify-between"
              >
                <span>{s.name}</span>
                {s.isolated && <span className="text-[10px] text-sev-3 uppercase">isolated</span>}
              </button>
            ))}
          </div>
        )}
      </div>

      {nearestSegment.isPending && (
        <div className="mt-2 text-[11px] text-ink-300">Finding nearest road...</div>
      )}

      {preview && (
        <div className="mt-2 p-2 border border-ground-300 bg-ground-000">
          <div className="text-[11px] text-ink-200">
            Nearest road: <span className="text-ink-000 font-data">{preview.road_class ?? "unclassified"}</span>
          </div>
          <div className="text-[11px] text-ink-300 font-data">
            way/{preview.osm_id ?? "?"} · {preview.distance_m.toFixed(0)}m away
          </div>
          {preview.blocked ? (
            <div className="text-[11px] text-sev-3 mt-1">Already blocked</div>
          ) : (
            <button
              onClick={handleBlock}
              disabled={blockSegment.isPending}
              className="w-full mt-1.5 h-6 px-2 border border-ground-400 bg-ground-300 text-ink-000 text-[11px] font-display uppercase tracking-wide hover:bg-ground-400 disabled:opacity-50"
            >
              {blockSegment.isPending ? "Blocking..." : "Block this road"}
            </button>
          )}
        </div>
      )}

      {blocked && blocked.length > 0 && (
        <div className="mt-3">
          <div className="text-[11px] text-ink-200 mb-1">Currently blocked ({blocked.length})</div>
          <div className="flex flex-col gap-1">
            {blocked.map((seg) => (
              <div
                key={seg.id}
                className="flex items-center justify-between gap-2 px-2 py-1 border-l-2 border-l-sev-3 bg-ground-000"
              >
                <span className="font-data text-[11px] text-ink-000">
                  {seg.road_class ?? "road"} · way/{seg.osm_id ?? seg.id}
                </span>
                <button
                  onClick={() => clearRoadSegment.mutate(seg.id)}
                  disabled={clearRoadSegment.isPending}
                  className="h-5 px-2 border border-ground-400 text-ink-200 text-[10px] font-display uppercase tracking-wide hover:bg-ground-200 disabled:opacity-50"
                >
                  Clear
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
