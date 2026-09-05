import { useEffect, useState } from "react"
import type { DisasterType } from "../lib/api"
import { useLiveRisk, useLiveRiskRange } from "../lib/hooks"
import { CollapsiblePanel } from "./CollapsiblePanel"

const SEV_BAND_COLOR = ["#4A5D52", "#C9A227", "#D97B1F", "#C23B22", "#7A1E14"]
const SEV_BAND_LABEL = ["Normal", "Watch", "Alert", "Warning", "Severe"]

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

export function LiveRiskPanel({ disasterType }: { disasterType: DisasterType }) {
  const [date, setDate] = useState(todayIso())
  const range = useLiveRiskRange()
  const liveRisk = useLiveRisk()

  useEffect(() => {
    if (range.data && date < range.data.min_date) setDate(range.data.min_date)
    if (range.data && date > range.data.max_date) setDate(range.data.max_date)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range.data])

  return (
    <CollapsiblePanel title="Live risk check" badge={liveRisk.data ? SEV_BAND_LABEL[liveRisk.data.max_band] : undefined}>
      <div className="px-3 py-2 flex flex-col gap-2">
        <p className="text-[11px] text-ink-300 leading-snug">
          Pick a date to check real live rainfall against the same terrain grid as the Titli scenario.
          {range.data && ` Available: ${range.data.min_date} to ${range.data.max_date}.`}
        </p>
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={date}
            min={range.data?.min_date}
            max={range.data?.max_date}
            onChange={(e) => setDate(e.target.value)}
            className="flex-1 bg-ground-300 text-ink-000 font-data text-[12px] h-6 px-1 border border-ground-400"
          />
          <button
            onClick={() => liveRisk.mutate({ date, disasterType })}
            disabled={liveRisk.isPending}
            className="h-6 px-2 bg-ground-300 border border-ground-400 text-ink-000 text-[11px] font-display uppercase tracking-wide hover:bg-ground-400 disabled:opacity-50"
          >
            {liveRisk.isPending ? "Checking..." : "Check"}
          </button>
        </div>

        {liveRisk.isError && (
          <p className="text-[11px] text-sev-3 leading-snug">
            {liveRisk.error instanceof Error ? liveRisk.error.message : "Could not check that date."}
          </p>
        )}

        {liveRisk.data && (
          <div className="flex flex-col gap-1.5 mt-1 pt-2 border-t border-ground-300">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 shrink-0" style={{ background: SEV_BAND_COLOR[liveRisk.data.max_band] }} />
              <span className="text-[12px] text-ink-100">{SEV_BAND_LABEL[liveRisk.data.max_band]} peak</span>
            </div>
            <p className="text-[12px] text-ink-000 leading-snug">{liveRisk.data.verdict}</p>
            <div className="font-data text-[11px] text-ink-200">
              {liveRisk.data.rain_72h_mm.toFixed(1)}mm rain (72h) · {liveRisk.data.elevated_cell_count} /{" "}
              {liveRisk.data.total_cells} cells elevated
            </div>
            <p className="text-[10px] text-ink-300 leading-snug">{liveRisk.data.note}</p>
          </div>
        )}
      </div>
    </CollapsiblePanel>
  )
}
