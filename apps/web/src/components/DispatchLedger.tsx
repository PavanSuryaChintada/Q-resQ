import { useLog } from "../lib/hooks"

function timeOf(iso: string): string {
  const d = new Date(iso)
  return d.toISOString().slice(11, 19)
}

export function DispatchLedger() {
  const { data: lines } = useLog()

  return (
    <aside className="w-[280px] shrink-0 border-l border-ground-300 bg-ground-100 flex flex-col h-full">
      <div className="h-8 flex items-center px-3 bg-ground-200 border-b border-ground-300">
        <span className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200">
          Dispatch ledger
        </span>
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-2 font-data text-[12px] leading-[1.45]">
        {!lines || lines.length === 0 ? (
          <p className="text-ink-300">No activity yet. Solves, fallbacks, and road closures appear here.</p>
        ) : (
          [...lines].reverse().map((line) => (
            <div
              key={line.id}
              className={`py-1 border-b border-ground-300/40 animate-[fadein_80ms_ease-out] ${
                line.severity >= 3 ? "border-l-2 border-l-sev-3 pl-2 -ml-2" : ""
              }`}
            >
              <span className="text-ink-300">{timeOf(line.at)}</span>{" "}
              <span className="text-ink-200 uppercase text-[10px] font-display tracking-wide">
                {line.channel}
              </span>
              <div className="text-ink-100">{line.message}</div>
            </div>
          ))
        )}
      </div>
    </aside>
  )
}
