const BANDS = [
  { label: "Normal", color: "#4A5D52" },
  { label: "Watch", color: "#C9A227" },
  { label: "Alert", color: "#D97B1F" },
  { label: "Warning", color: "#C23B22" },
  { label: "Severe", color: "#7A1E14" },
]

export function LayersPanel() {
  return (
    <div className="border-b border-ground-300">
      <div className="h-8 flex items-center px-3 bg-ground-200 border-b border-ground-300">
        <span className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200">
          Risk
        </span>
      </div>
      <div className="px-3 py-2">
        {BANDS.map((b, i) => (
          <div key={b.label} className="flex items-center gap-2 py-0.5">
            <span className="w-3 h-3 inline-block shrink-0" style={{ background: b.color }} />
            <span className="text-[12px] text-ink-100">{b.label}</span>
            <span className="ml-auto font-data text-[11px] text-ink-300">{i}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
