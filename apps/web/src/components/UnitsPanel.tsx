import { useUnits } from "../lib/hooks"

const STATUS_COLOR: Record<string, string> = {
  available: "#5C8A6E",
  assigned: "#C9A227",
  en_route: "#C9A227",
  returning: "#9A968D",
  offline: "#6B6862",
}

export function UnitsPanel() {
  const { data: units } = useUnits()

  return (
    <div className="flex-1 min-h-0 flex flex-col border-t border-ground-300">
      <div className="h-8 flex items-center px-3 bg-ground-200 border-b border-ground-300">
        <span className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200">
          Units
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {(units ?? []).map((u) => (
          <div key={u.id} className="flex items-center gap-2 px-3 py-1.5 border-b border-ground-300/50 text-[13px]">
            <span
              className="w-2 h-2 inline-block shrink-0"
              style={{ background: STATUS_COLOR[u.status] ?? "#6B6862" }}
            />
            <span className="text-ink-000 truncate">{u.label}</span>
            <span className="ml-auto text-ink-300 font-data text-[11px]">{u.status}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
