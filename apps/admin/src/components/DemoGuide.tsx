import { useState } from "react"

interface Step {
  title: string
  say: string
  doThis: string
}

// Demo run sheet for the landslide early warning system - 5 minutes
// Matches docs/DEMO_NARRATIVE.md
const STEPS: Step[] = [
  {
    title: "Risk map, Aizawl",
    say: "Aizawl. Built on cut slopes, on a ridge, in monsoon country. 284,000 cells at 100 metres.",
    doThis: "Click any coloured cell on the map. The panel shows slope, curvature, and cut-slope proximity.",
  },
  {
    title: "Cut-slope proximity",
    say: "The brief names unplanned hill cutting. It's a first-class feature, and it flags 3.6 % of the district.",
    doThis: "Point at the is_cut_slope field in the cell detail panel.",
  },
  {
    title: "Provenance flag",
    say: "This cell says index, not model. We have 69 positive samples for this district — not enough to train something that survives spatial cross-validation. The training pipeline is built. It needs inventory, not code.",
    doThis: "Point at the provenance field in the cell detail panel.",
  },
  {
    title: "Deformation corridor",
    say: "This is not susceptibility. This is measured ground movement from Sentinel-1 interferometry. This slope is moving.",
    doThis: "Toggle the Deformation layer and click a point in the corridor.",
  },
  {
    title: "Time series",
    say: "Steady creep is normal on a hillslope. Acceleration is not. That distinction is the early warning — and it's why we don't just flag everything that moves.",
    doThis: "Point at the velocity and acceleration fields in the deformation detail panel.",
  },
  {
    title: "Corridor boundary",
    say: "Outside this boundary the layer is empty. We processed one corridor. We don't interpolate across ground we didn't measure.",
    doThis: "Pan outside the corridor boundary and observe the empty layer.",
  },
  {
    title: "Block NH6",
    say: "Now a landslide takes the highway. This is not hypothetical — NH6 is the Aizawl–Silchar route and it closes to landslides most monsoons.",
    doThis: "Use the demo trigger to block NH6 (way/24583261).",
  },
  {
    title: "Isolation view",
    say: "Lenchim. Tawizo. Mualpheng. Three villages, and there is no second route in the real road network. In a flood people self-evacuate. On a ridge, one road going removes the only option. That's a separate axis of urgency and it enters the priority score directly.",
    doThis: "Point at the isolation scores for the three settlements in the isolation view.",
  },
  {
    title: "Dispatch",
    say: "Allocation across those three. Formulated as a QUBO, running on classical solvers, hardware-ready for quantum backends.",
    doThis: "Click Dispatch and observe the allocation to the isolated settlements.",
  },
  {
    title: "Alerts",
    say: "CAP format — the standard Indian agencies already use. Geo-fenced, evaluated on-device so it works with no signal.",
    doThis: "Point at the CAP payload preview in the alerts panel.",
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
