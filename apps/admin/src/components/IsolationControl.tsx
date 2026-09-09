import { useState } from "react"

interface Props {
  onBlockNH6: () => void
  onClearNH6: () => void
  isolatedSettlements: string[]
  isBlocked: boolean
  onTriggerAlert?: (settlement: string) => void
}

export function IsolationControl({ onBlockNH6, onClearNH6, isolatedSettlements, isBlocked, onTriggerAlert }: Props) {
  const [blocking, setBlocking] = useState(false)
  const [alerting, setAlerting] = useState<string | null>(null)

  const handleBlock = async () => {
    setBlocking(true)
    await onBlockNH6()
    setBlocking(false)
  }

  const handleClear = async () => {
    setBlocking(true)
    await onClearNH6()
    setBlocking(false)
  }

  const handleTriggerAlert = async (settlement: string) => {
    setAlerting(settlement)
    if (onTriggerAlert) {
      await onTriggerAlert(settlement)
    }
    setAlerting(null)
  }

  return (
    <div className="border-t border-ground-300 p-3">
      <div className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200 mb-2">
        Road Isolation Control
      </div>
      <div className="mb-2 text-[12px] text-ink-300">
        NH6 is the Aizawl-Silchar route and closes to landslides most monsoons.
        Blocking it isolates: {isolatedSettlements.join(", ")}
      </div>
      <div className="flex gap-2">
        {!isBlocked ? (
          <button
            onClick={handleBlock}
            disabled={blocking}
            className="flex-1 px-3 py-2 bg-ground-300 border border-ground-400 text-ink-000 text-[12px] font-display uppercase tracking-wide hover:bg-ground-400 disabled:opacity-50"
          >
            {blocking ? "Blocking..." : "Block NH6"}
          </button>
        ) : (
          <button
            onClick={handleClear}
            disabled={blocking}
            className="flex-1 px-3 py-2 bg-ground-300 border border-ground-400 text-ink-000 text-[12px] font-display uppercase tracking-wide hover:bg-ground-400 disabled:opacity-50"
          >
            {blocking ? "Clearing..." : "Clear NH6"}
          </button>
        )}
      </div>
      {isBlocked && (
        <div className="mt-2 border border-ground-300 bg-ground-000">
          <div className="text-[11px] text-ink-200 px-2 pt-2">Isolated settlements:</div>
          <div className="flex flex-col">
            {isolatedSettlements.map((s) => (
              <div
                key={s}
                className="flex items-center justify-between gap-2 px-2 py-1.5 mt-1 border-l-2 border-l-sev-3 bg-ground-100"
              >
                <span className="font-data text-[12px] text-ink-000">{s}</span>
                <button
                  onClick={() => handleTriggerAlert(s)}
                  disabled={alerting === s}
                  className="h-6 px-2 border border-sev-3 text-sev-3 text-[11px] font-display uppercase tracking-wide hover:bg-ground-200 disabled:opacity-50"
                >
                  {alerting === s ? "Alerting..." : "Trigger alert"}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
