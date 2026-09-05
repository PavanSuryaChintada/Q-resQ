import type { DisasterType } from "../lib/api"
import { useRiskCellDetail } from "../lib/hooks"
import { CollapsiblePanel } from "./CollapsiblePanel"

const SEV_BAND_COLOR = ["#4A5D52", "#C9A227", "#D97B1F", "#C23B22", "#7A1E14"]
const SEV_BAND_LABEL = ["Normal", "Watch", "Alert", "Warning", "Severe"]

export function RiskCellPanel({ cellId, disasterType }: { cellId: number | null; disasterType: DisasterType }) {
  const { data: detail, isFetching } = useRiskCellDetail(cellId, disasterType)

  return (
    <CollapsiblePanel title="Cell detail" badge={detail ? SEV_BAND_LABEL[detail.risk_band] : undefined}>
      <div className="px-3 py-2">
        {cellId === null && (
          <p className="text-[12px] text-ink-300">Click a risk cell on the map to see its score and the terrain/rainfall features behind it.</p>
        )}
        {cellId !== null && isFetching && <p className="text-[12px] text-ink-300">Loading...</p>}
        {detail && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 shrink-0" style={{ background: SEV_BAND_COLOR[detail.risk_band] }} />
              <span className="font-data text-[16px] text-ink-000">{detail.risk_score.toFixed(3)}</span>
              <span className="text-[12px] text-ink-200">{SEV_BAND_LABEL[detail.risk_band]}</span>
            </div>
            <div className="text-[11px] font-display uppercase tracking-wide text-ink-300 mt-1">
              Top contributing features
            </div>
            {detail.top_features.map((f) => (
              <div key={f.name} className="flex justify-between text-[12px] font-data">
                <span className="text-ink-100">{f.name}</span>
                <span className="text-ink-200">
                  val {f.value.toFixed(2)} · +{f.contribution.toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </CollapsiblePanel>
  )
}
