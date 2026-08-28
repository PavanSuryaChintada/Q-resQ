import { useState } from "react"

interface Step {
  title: string
  say: string
  doThis: string
}

// Matches what's actually built and real-data-backed today - not the
// full docs/WORKFLOW.md #8 script, which also covers offline/PWA and
// road-reflooding that were cut from this build's scope.
const STEPS: Step[] = [
  {
    title: "Risk map",
    say: "Cyclone Titli, Srikakulam, 11 October 2018. Every cell here is computed from the real Copernicus DEM and real IMD rainfall for this event - not placeholder data.",
    doThis: "Click any coloured cell on the map. The panel on the left shows its score and the top terrain/rainfall features behind it.",
  },
  {
    title: "Requests, triaged",
    say: "Every project stops at the map. A map doesn't rescue anyone - so every incoming request gets a severity score, and the queue is ranked by it.",
    doThis: "Point at the Request Queue table - severity-ordered, people count, category.",
  },
  {
    title: "Dispatch",
    say: "This partitions requests into zones and solves each one - real QUBO, not a lookup table. Try switching the backend to qaoa and watch it actually run.",
    doThis: "Pick a backend in the dropdown, click Dispatch. Toggle Show Routes to see the assignments on the map.",
  },
  {
    title: "Benchmark - the honest part",
    say: "This is the whole pitch. QAOA reaches parity with OR-Tools at this scale - it does not beat it, and we show that rather than hide it.",
    doThis: "Click Benchmark (incl. qaoa). Point out the qubit count column and that no row is hidden or reordered to make quantum look better.",
  },
  {
    title: "Dispatch ledger",
    say: "Append-only. Every solve, every fallback, every decision - in order, on the right rail, the whole time.",
    doThis: "Point at the ledger. Nothing on this panel is ever edited or deleted after the fact.",
  },
]

export function DemoGuide({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(0)
  const current = STEPS[step]

  return (
    <div className="absolute top-0 left-0 right-0 z-10 bg-ground-100 border-b border-ground-300">
      <div className="h-8 flex items-center px-3 bg-ground-200 border-b border-ground-300 gap-2">
        <span className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200">
          Demo guide
        </span>
        <span className="font-data text-[11px] text-ink-300">
          step {step + 1} of {STEPS.length}
        </span>
        <button
          onClick={onClose}
          className="ml-auto h-6 px-2 bg-transparent border border-ground-300 text-ink-200 text-[11px] font-display uppercase tracking-wide hover:bg-ground-300"
        >
          Close
        </button>
      </div>
      <div className="px-4 py-3 flex items-start gap-6">
        <div className="flex-1 min-w-0">
          <div className="font-display font-semibold text-[15px] text-ink-000 mb-1">
            {current.title}
          </div>
          <div className="text-[13px] text-ink-100 leading-relaxed mb-2">
            {current.say}
          </div>
          <div className="text-[12px] text-ink-300">
            <span className="uppercase tracking-wide text-[10px] font-display text-ink-300">Do this: </span>
            {current.doThis}
          </div>
        </div>
        <div className="flex flex-col gap-2 shrink-0">
          <button
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
            className="h-7 px-3 bg-ground-300 border border-ground-400 text-ink-000 text-[11px] font-display uppercase tracking-wide hover:bg-ground-400 disabled:opacity-40"
          >
            Previous
          </button>
          <button
            onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
            disabled={step === STEPS.length - 1}
            className="h-7 px-3 bg-ground-300 border border-ground-400 text-ink-000 text-[11px] font-display uppercase tracking-wide hover:bg-ground-400 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
