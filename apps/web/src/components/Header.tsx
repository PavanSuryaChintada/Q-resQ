import type { DisasterType } from "../lib/api"

const DISASTER_LABEL: Record<DisasterType, string> = {
  cyclone: "Cyclone",
  flood: "Flood",
  urban_flooding: "Urban flooding",
  landslide: "Landslide",
}

interface Props {
  view: "dashboard" | "architecture" | "flow" | "summary"
  onViewChange: (v: "dashboard" | "architecture" | "flow" | "summary") => void
  guideOpen: boolean
  onToggleGuide: () => void
  disasterType: DisasterType
  onDisasterTypeChange: (t: DisasterType) => void
}

export function Header({
  view,
  onViewChange,
  guideOpen,
  onToggleGuide,
  disasterType,
  onDisasterTypeChange,
}: Props) {
  return (
    <header className="h-12 shrink-0 flex items-center px-4 bg-ground-100 border-b border-ground-300 gap-4">
      <span className="font-display font-semibold text-[15px] tracking-[0.02em] text-ink-000">Q-resQ</span>
      <select
        value={disasterType}
        onChange={(e) => onDisasterTypeChange(e.target.value as DisasterType)}
        className="h-7 px-2 bg-ground-300 border border-ground-400 text-ink-000 text-[11px] font-display uppercase tracking-wide"
        title="Same real Srikakulam terrain and rainfall, re-weighted for this hazard type"
      >
        {(Object.keys(DISASTER_LABEL) as DisasterType[]).map((t) => (
          <option key={t} value={t}>
            {DISASTER_LABEL[t]}
          </option>
        ))}
      </select>
      <span className="font-data text-[12px] text-ink-200">
        SRIKAKULAM {disasterType === "cyclone" ? "· 11 OCT 2018 REPLAY" : "· SCENARIO"}
      </span>
      {view === "dashboard" && (
        <button
          onClick={onToggleGuide}
          className={`h-7 px-3 text-[11px] font-display uppercase tracking-wide border ${
            guideOpen
              ? "bg-ground-300 border-ground-400 text-ink-000"
              : "bg-transparent border-ground-300 text-ink-200 hover:bg-ground-200"
          }`}
        >
          {guideOpen ? "Hide demo guide" : "Demo guide"}
        </button>
      )}
      <nav className="ml-auto flex gap-1">
        <button
          onClick={() => onViewChange("dashboard")}
          className={`h-7 px-3 text-[11px] font-display uppercase tracking-wide border ${
            view === "dashboard"
              ? "bg-ground-300 border-ground-400 text-ink-000"
              : "bg-transparent border-ground-300 text-ink-200 hover:bg-ground-200"
          }`}
        >
          Dashboard
        </button>
        <button
          onClick={() => onViewChange("flow")}
          className={`h-7 px-3 text-[11px] font-display uppercase tracking-wide border ${
            view === "flow"
              ? "bg-ground-300 border-ground-400 text-ink-000"
              : "bg-transparent border-ground-300 text-ink-200 hover:bg-ground-200"
          }`}
        >
          Flow
        </button>
        <button
          onClick={() => onViewChange("architecture")}
          className={`h-7 px-3 text-[11px] font-display uppercase tracking-wide border ${
            view === "architecture"
              ? "bg-ground-300 border-ground-400 text-ink-000"
              : "bg-transparent border-ground-300 text-ink-200 hover:bg-ground-200"
          }`}
        >
          Architecture
        </button>
        <button
          onClick={() => onViewChange("summary")}
          className={`h-7 px-3 text-[11px] font-display uppercase tracking-wide border ${
            view === "summary"
              ? "bg-ground-300 border-ground-400 text-ink-000"
              : "bg-transparent border-ground-300 text-ink-200 hover:bg-ground-200"
          }`}
        >
          Solution summary
        </button>
      </nav>
    </header>
  )
}
