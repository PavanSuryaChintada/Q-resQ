import { useState } from "react"
import { useBlockSegment, useCreateRequest, useNearestSegment, useReports } from "../lib/hooks"
import { api } from "../lib/api"

const STATUS_COLOR: Record<string, string> = {
  pending: "#C9A227",
  verified: "#5C8A6E",
  dismissed: "#6B6862",
  duplicate: "#9A968D",
}

const KIND_COLOR: Record<string, string> = {
  crack: "#C9A227",
  slope_movement: "#D97B1F",
  road_blocked: "#C23B22",
  water_seepage: "#4A5D52",
  other: "#6B6862",
}

// Approving a report creates a real dispatch request at the reported
// location - people_count is a placeholder (a photo report carries no
// headcount) that the officer is expected to correct once assessed.
const REPORT_KIND_TO_CATEGORY: Record<string, "medical" | "stranded" | "evacuation"> = {
  crack: "evacuation",
  slope_movement: "evacuation",
  road_blocked: "stranded",
  water_seepage: "stranded",
  other: "stranded",
}

interface Props {
  onReportSelect: (reportId: string) => void
  selectedReportId: string | null
}

export function ReportsPanel({ onReportSelect, selectedReportId }: Props) {
  const { data: reports } = useReports()
  const createRequest = useCreateRequest()
  const nearestSegment = useNearestSegment()
  const blockSegment = useBlockSegment()
  const [reviewing, setReviewing] = useState<string | null>(null)
  const [blockingReportId, setBlockingReportId] = useState<string | null>(null)
  const [filter, setFilter] = useState<"all" | "pending" | "verified" | "dismissed">("pending")

  const handleBlockRoad = async (reportId: string) => {
    const report = reports?.find((r) => r.id === reportId)
    if (!report) return
    setBlockingReportId(reportId)
    try {
      const segment = await nearestSegment.mutateAsync({ lat: report.location[0], lon: report.location[1] })
      if (!segment.blocked) {
        await blockSegment.mutateAsync({ segmentId: segment.id, reason: "reported" })
      }
      await handleStatusChange(reportId, "verified")
    } finally {
      setBlockingReportId(null)
    }
  }

  const handleStatusChange = async (reportId: string, newStatus: string) => {
    try {
      await api.updateReport(reportId, newStatus)
      // The query will auto-refetch due to the hook
    } catch (error) {
      console.error("Failed to update report:", error)
    }
    setReviewing(null)
  }

  const handleApprove = async (reportId: string) => {
    const report = reports?.find(r => r.id === reportId)
    if (!report) return
    await createRequest.mutateAsync({
      id: crypto.randomUUID(),
      location: report.location,
      people_count: 1,
      category: REPORT_KIND_TO_CATEGORY[report.kind] ?? "stranded",
      note: `From citizen report: ${report.kind.replace("_", " ")}${report.note ? ` - ${report.note}` : ""}`,
      created_at: new Date().toISOString(),
    })
    await handleStatusChange(reportId, "verified")
  }

  const filtered = filter === "all"
    ? (reports ?? [])
    : (reports ?? []).filter(r => r.status === filter)

  const pendingCount = (reports ?? []).filter(r => r.status === "pending").length

  return (
    <div className="flex-1 flex flex-col border-t border-ground-300 min-h-0">
      <div className="h-8 flex items-center justify-between px-3 bg-ground-200 border-b border-ground-300">
        <span className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200">
          Citizen Reports
        </span>
        <div className="flex items-center gap-2">
          <span className="w-px h-4 bg-ground-400" />
          <select
            className="bg-ground-300 text-ink-000 text-[12px] font-body h-6 px-1 border border-ground-400"
            value={filter}
            onChange={(e) => setFilter(e.target.value as typeof filter)}
          >
            <option value="all">All ({reports?.length || 0})</option>
            <option value="pending">Pending ({pendingCount})</option>
            <option value="verified">Verified</option>
            <option value="dismissed">Dismissed</option>
          </select>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="px-4 py-8 text-center text-ink-300 text-[13px]">
            No reports in this view
          </div>
        ) : (
          filtered.map((r) => {
            const isSelected = r.id === selectedReportId
            const isReviewing = reviewing === r.id

            return (
              <div
                key={r.id}
                onClick={() => onReportSelect(r.id)}
                className={`border-b border-ground-300 cursor-pointer hover:bg-ground-200 ${
                  isSelected ? "bg-ground-200" : ""
                }`}
                style={{ borderLeft: `2px solid ${STATUS_COLOR[r.status]}` }}
              >
                <div className="px-3 py-2">
                  <div className="flex items-center gap-2 mb-1">
                    <div
                      className="w-3 h-3 shrink-0"
                      style={{ backgroundColor: KIND_COLOR[r.kind] || "#6B6862" }}
                    />
                    <span className="text-[13px] font-medium capitalize">{r.kind.replace("_", " ")}</span>
                    <span className="ml-auto text-[11px] text-ink-300 font-data">
                      {new Date(r.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="text-[12px] text-ink-200 mb-1">
                    {r.note || "No note provided"}
                  </div>
                  {r.media_url && r.media_type === "image" && (
                    <img
                      src={r.media_url}
                      alt={`${r.kind} report photo`}
                      className="w-full max-h-32 object-cover border border-ground-300 mb-1"
                    />
                  )}
                  <div className="flex items-center gap-2 text-[11px] text-ink-300">
                    <span className="font-data">
                      {r.location[0].toFixed(4)}, {r.location[1].toFixed(4)}
                    </span>
                    <span className="text-ground-400">|</span>
                    <span className="capitalize">{r.status}</span>
                  </div>

                  {isReviewing && r.status === "pending" && (
                    <div className="mt-2 pt-2 border-t border-ground-300">
                      {r.kind === "road_blocked" && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleBlockRoad(r.id)
                          }}
                          disabled={blockingReportId === r.id}
                          className="w-full mb-2 px-2 py-1 border border-sev-3 text-sev-3 text-[11px] hover:bg-ground-200 disabled:opacity-50"
                        >
                          {blockingReportId === r.id ? "Finding + blocking nearest road..." : "Block nearest road (reported)"}
                        </button>
                      )}
                      <div className="flex gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleApprove(r.id)
                          }}
                          className="flex-1 px-2 py-1 bg-ground-300 border border-ground-400 text-[11px] hover:bg-ground-400"
                        >
                          ✓ Approve & Dispatch
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleStatusChange(r.id, "verified")
                          }}
                          className="flex-1 px-2 py-1 bg-ground-300 border border-ground-400 text-[11px] hover:bg-ground-400"
                        >
                          ✓ Verify Only
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleStatusChange(r.id, "dismissed")
                          }}
                          className="flex-1 px-2 py-1 bg-ground-300 border border-ground-400 text-[11px] hover:bg-ground-400"
                        >
                          ✕ Dismiss
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setReviewing(null)
                          }}
                          className="px-2 py-1 bg-ground-300 border border-ground-400 text-[11px] hover:bg-ground-400"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}

                  {!isReviewing && r.status === "pending" && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setReviewing(r.id)
                      }}
                      className="mt-2 w-full px-2 py-1 bg-ground-300 border border-ground-400 text-[11px] hover:bg-ground-400"
                    >
                      Review
                    </button>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
