import { useState } from "react"
import type { RequestOut } from "../lib/api"

const SEV_COLORS = ["#4A5D52", "#C9A227", "#D97B1F", "#C23B22", "#7A1E14"]
const SEV_LABEL = ["Normal", "Watch", "Alert", "Warning", "Severe"]

interface Props {
  requests: RequestOut[]
  onRequestSelect: (requestId: string) => void
  selectedRequestId: string | null
}

export function RequestCarousel({ requests, onRequestSelect, selectedRequestId }: Props) {
  const [currentIndex, setCurrentIndex] = useState(0)
  
  if (!requests || requests.length === 0) {
    return (
      <div className="border border-ground-300 bg-ground-100 p-4">
        <p className="text-[12px] text-ink-300">No requests in queue</p>
      </div>
    )
  }

  const currentRequest = requests[currentIndex]
  const severityBand = currentRequest.severity != null && currentRequest.severity >= 0
    ? Math.min(Math.floor(currentRequest.severity * 5), 4)
    : 0
  const isSelected = currentRequest.id === selectedRequestId

  const handleNext = () => {
    const nextIndex = (currentIndex + 1) % requests.length
    setCurrentIndex(nextIndex)
  }

  const handlePrevious = () => {
    const prevIndex = (currentIndex - 1 + requests.length) % requests.length
    setCurrentIndex(prevIndex)
  }

  const handleGoToLocation = () => {
    console.log("Go to location clicked for request:", currentRequest.id, "location:", currentRequest.location)
    onRequestSelect(currentRequest.id)
  }

  return (
    <div className="border border-ground-300 bg-ground-100 p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200">
          Request {currentIndex + 1} of {requests.length}
        </span>
        <div className="flex gap-2">
          <button
            onClick={handlePrevious}
            className="h-6 px-3 bg-ground-300 border border-ground-400 text-ink-000 text-[11px] font-display uppercase tracking-wide hover:bg-ground-400"
          >
            Previous
          </button>
          <button
            onClick={handleNext}
            className="h-6 px-3 bg-ground-300 border border-ground-400 text-ink-000 text-[11px] font-display uppercase tracking-wide hover:bg-ground-400"
          >
            Next
          </button>
          <button
            onClick={handleGoToLocation}
            className="h-6 px-3 bg-ground-400 border border-ground-500 text-ink-000 text-[11px] font-display uppercase tracking-wide hover:bg-ground-500"
          >
            Go
          </button>
        </div>
      </div>

      <div className={`border bg-ground-000 p-3 ${isSelected ? "border-ink-000" : "border-ground-300"}`}>
        <div className="flex items-center gap-2 mb-2">
          <span
            className="w-4 h-4"
            style={{ background: SEV_COLORS[severityBand] }}
          />
          <span className="font-display font-semibold text-[13px] text-ink-000">
            {SEV_LABEL[severityBand]} Severity
          </span>
          {isSelected && (
            <span className="font-display text-[10px] uppercase tracking-wide text-ink-200">
              selected on map
            </span>
          )}
          <span className="font-data text-[12px] text-ink-200 ml-auto">
            {currentRequest.severity?.toFixed(3)}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-[12px]">
          <div>
            <span className="font-display uppercase tracking-wide text-ink-300 text-[10px]">People</span>
            <div className="font-data text-ink-000">{currentRequest.people_count}</div>
          </div>
          <div>
            <span className="font-display uppercase tracking-wide text-ink-300 text-[10px]">Category</span>
            <div className="font-data text-ink-000 capitalize">{currentRequest.category}</div>
          </div>
          <div>
            <span className="font-display uppercase tracking-wide text-ink-300 text-[10px]">Status</span>
            <div className="font-data text-ink-000 capitalize">{currentRequest.status}</div>
          </div>
          <div>
            <span className="font-display uppercase tracking-wide text-ink-300 text-[10px]">ID</span>
            <div className="font-data text-ink-200">{currentRequest.id.slice(0, 8)}</div>
          </div>
        </div>

        {currentRequest.note && (
          <div className="mt-2 pt-2 border-t border-ground-300">
            <span className="font-display uppercase tracking-wide text-ink-300 text-[10px]">Note</span>
            <div className="text-[12px] text-ink-200 mt-1">{currentRequest.note}</div>
          </div>
        )}

        <div className="mt-3 pt-2 border-t border-ground-300 text-[11px] font-data text-ink-300">
          <div>Severity breakdown:</div>
          <div className="grid grid-cols-2 gap-1 mt-1">
            <div>People: {currentRequest.sev_people?.toFixed(3) || "N/A"}</div>
            <div>Category: {currentRequest.sev_category?.toFixed(3) || "N/A"}</div>
            <div>Area risk: {currentRequest.sev_area_risk?.toFixed(3) || "N/A"}</div>
            <div>Wait time: {currentRequest.sev_wait?.toFixed(3) || "N/A"}</div>
          </div>
        </div>
      </div>
    </div>
  )
}