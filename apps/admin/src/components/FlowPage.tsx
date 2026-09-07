import { useState } from "react"

interface FlowStep {
  id: number
  title: string
  description: string
  details: string[]
  input: string[]
  output: string
}

const FLOW_STEPS: FlowStep[] = [
  {
    id: 1,
    title: "Risk Model",
    description: "Terrain analysis and rainfall data processed through ML to generate flood risk scores",
    details: [
      "DEM (Digital Elevation Model) provides terrain height data",
      "HAND (Height Above Nearest Drainage) computed via pysheds",
      "Slope and Topographic Wetness Index derived from terrain",
      "72-hour rainfall data from IMD RF25 gridded dataset",
      "Physical risk formula: HAND 40% + rain 30% + slope 15% + dist-stream 10% + drainage 5%",
      "LightGBM model trained on SAR flood labels (when available)"
    ],
    input: ["DEM (elevation)", "Rainfall data", "Slope & drainage"],
    output: "Risk map with cell scores"
  },
  {
    id: 2,
    title: "Triage & Roads",
    description: "Request severity scoring and flood-aware road network passability computation",
    details: [
      "Severity computed from: people count + category + area risk + wait time",
      "Medical requests weighted highest (1.0), stranded (0.7), evacuation (0.5)",
      "Components normalised against current queue maximums for relative scoring",
      "Road network extracted from OpenStreetMap via osmnx",
      "Edge weights updated based on flood depth and passability",
      "Travel times computed over flood-aware graph, not straight-line distance"
    ],
    input: ["Risk scores", "Rescue requests", "Road network"],
    output: "Severity per request + travel times"
  },
  {
    id: 3,
    title: "Partition",
    description: "Geographic clustering into zones of ≤5 requests and ≤4 units for parallel solving",
    details: [
      "Constrained k-means clustering with geographic constraints",
      "Zone cap: ≤ 5 requests, ≤ 4 units per zone (20 qubits target)",
      "Balances severity total across zones for fair distribution",
      "Enables horizontal scaling as request count grows",
      "Qubit count per solve stays constant regardless of total requests",
      "Zones solved in parallel using ProcessPoolExecutor"
    ],
    input: ["Requests with severity", "Available units", "Travel times"],
    output: "Optimized zones"
  },
  {
    id: 4,
    title: "QUBO Solve",
    description: "Quantum-inspired optimization per zone with fallback chain (QAOA → annealing → greedy)",
    details: [
      "QUBO formulation: minimise cost + penalty constraints",
      "Cost: maximise severity assignment, minimise travel time",
      "Constraints: each request served at most once, each unit dispatched at most once",
      "Auto-tuned penalty weights from objective bound (λ = 1.2 × bound)",
      "Fallback chain: QAOA (10s timeout) → Simulated Annealing → Greedy",
      "Greedy solver has no dependencies, never fails"
    ],
    input: ["Zone requests", "Zone units", "Travel costs"],
    output: "Unit-to-request assignments"
  },
  {
    id: 5,
    title: "Route & Validate",
    description: "Shortest path computation and constraint validation before final dispatch",
    details: [
      "Shortest path computed over flood-aware road network",
      "Constraint validation: no double-assignment of units or requests",
      "If validation fails, falls back to next solver in chain",
      "Routes returned as LineString geometries for map display",
      "Assignment persisted to database with round metadata",
      "Realtime broadcast to all connected dashboard clients"
    ],
    input: ["Assignments", "Flood-aware graph"],
    output: "Validated routes for dispatch"
  }
]

export function FlowPage() {
  const [currentStep, setCurrentStep] = useState<number>(0)
  const currentStepData = FLOW_STEPS[currentStep]

  const handleNext = () => {
    if (currentStep < FLOW_STEPS.length - 1) {
      setCurrentStep(currentStep + 1)
    } else {
      setCurrentStep(0) // Loop back to start
    }
  }

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    } else {
      setCurrentStep(FLOW_STEPS.length - 1) // Loop to end
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <h1 className="font-display font-semibold text-[18px] text-ink-000 mb-1">Pipeline Flow</h1>
      <p className="text-[13px] text-ink-200 mb-6 max-w-2xl">
        Step-by-step visualization of how prediction and decision-making work together to prioritise rescue operations.
      </p>
      
      {/* Progress indicator */}
      <div className="mb-6 flex items-center gap-2">
        {FLOW_STEPS.map((step, index) => (
          <div
            key={step.id}
            className={`h-1 flex-1 ${
              index <= currentStep ? "bg-ground-400" : "bg-ground-300"
            }`}
          />
        ))}
      </div>

      {/* Main container */}
      <div className="max-w-4xl">
        <div className="border border-ground-300 bg-ground-100 p-6">
          {/* Step header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 flex items-center justify-center bg-ground-400 text-ink-000 font-display font-semibold text-[16px]">
                {currentStepData.id}
              </div>
              <div>
                <h2 className="font-display font-semibold text-[16px] text-ink-000">{currentStepData.title}</h2>
                <p className="text-[12px] text-ink-300">Step {currentStep + 1} of {FLOW_STEPS.length}</p>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handlePrevious}
                className="h-8 px-4 bg-ground-300 border border-ground-400 text-ink-000 text-[12px] font-display uppercase tracking-wide hover:bg-ground-400"
              >
                Previous
              </button>
              <button
                onClick={handleNext}
                className="h-8 px-4 bg-ground-400 border border-ground-500 text-ink-000 text-[12px] font-display uppercase tracking-wide hover:bg-ground-500"
              >
                {currentStep === FLOW_STEPS.length - 1 ? "Start Over" : "Next"}
              </button>
            </div>
          </div>

          {/* Step description */}
          <p className="text-[14px] text-ink-200 leading-relaxed mb-6">
            {currentStepData.description}
          </p>

          {/* Detailed explanation */}
          <div className="mb-6">
            <h3 className="font-display font-semibold text-[13px] text-ink-000 mb-3">How it works</h3>
            <ul className="space-y-2">
              {currentStepData.details.map((detail, index) => (
                <li key={index} className="flex items-start gap-2 text-[12px] text-ink-200">
                  <span className="text-ground-400 mt-1">→</span>
                  <span>{detail}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Input/Output */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="font-display font-semibold text-[13px] text-ink-000 mb-2">Input</h3>
              <div className="flex flex-wrap gap-1">
                {currentStepData.input.map((item, index) => (
                  <span key={index} className="px-2 py-1 bg-ground-200 text-ink-200 text-[11px]">
                    {item}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <h3 className="font-display font-semibold text-[13px] text-ink-000 mb-2">Output</h3>
              <span className="px-2 py-1 bg-ground-300 text-ink-100 text-[11px]">
                {currentStepData.output}
              </span>
            </div>
          </div>
        </div>

        {/* Key insight */}
        <div className="mt-6 p-4 border border-ground-300 bg-ground-100">
          <h3 className="font-display font-semibold text-[13px] text-ink-000 mb-2">Key insight</h3>
          <p className="text-[12px] text-ink-200 leading-relaxed">
            The pipeline loops back: as flood conditions change, road passability updates, which changes travel costs, 
            requiring re-optimization. This is why the dispatch engine exists — static planning fails when the terrain itself is dynamic.
          </p>
        </div>
      </div>
    </div>
  )
}