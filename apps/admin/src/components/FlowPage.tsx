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
    title: "Terrain",
    description: "Copernicus DEM at 30 m, resampled to a 100 m analysis grid. 284,070 cells.",
    details: [
      "DEM (Digital Elevation Model) provides terrain height data",
      "Slope, aspect (encoded as sin/cos), plan and profile curvature derived",
      "LS factor (slope length factor) computed",
      "HAND (Height Above Nearest Drainage) computed via pysheds",
      "Topographic Wetness Index (TWI) derived",
      "Distance to stream computed",
      "Distance to road cut: within 50 m of road centreline and steeper than 25°",
      "All geometric derivations — deterministic, not learned"
    ],
    input: ["Copernicus DEM 30 m"],
    output: "100 m grid with terrain features"
  },
  {
    id: 2,
    title: "Susceptibility",
    description: "Physical index over slope, profile curvature, cut-slope proximity, forest cover and LS factor.",
    details: [
      "Physical index: weighted sum of terrain features",
      "Weights: slope 0.35, profile curvature 0.25, cut-slope 0.20, forest cover 0.15, LS factor 0.05",
      "Lithology weight renormalised when unavailable (not fabricated)",
      "Risk score 0–1 per cell, banded to IMD warning ladder",
      "Every cell carries provenance flag: index or model",
      "When inventory data allows, LightGBM model replaces index"
    ],
    input: ["Terrain features", "Forest cover", "Lithology (optional)"],
    output: "Susceptibility per cell"
  },
  {
    id: 3,
    title: "Trigger",
    description: "Rainfall accumulation at 1, 3, 7 and 15 days, plus maximum hourly intensity and soil moisture.",
    details: [
      "Rainfall accumulation at multiple time windows",
      "Maximum hourly intensity captured",
      "Soil moisture from SMAP and ERA5-Land (satellite-derived)",
      "The 15-day window matters: slopes fail after sustained saturation followed by intensity spike",
      "risk = susceptibility × trigger, both components exposed separately",
      "Trigger index runs independently of susceptibility"
    ],
    input: ["Rainfall data", "Soil moisture"],
    output: "Trigger index per cell"
  },
  {
    id: 4,
    title: "Deformation",
    description: "Sentinel-1 InSAR, SBAS, pre-computed for demo corridor.",
    details: [
      "Line-of-sight velocity computed from Sentinel-1 interferometry",
      "Acceleration derived from velocity change over time",
      "Points classified: stable (below 5 mm/yr), creeping, accelerating",
      "Acceleration is the alert signal, not movement itself",
      "Points below 0.3 coherence discarded (vegetated hillslopes decorrelate)",
      "Renders only inside processed corridor, empty outside"
    ],
    input: ["Sentinel-1 SAR data"],
    output: "Deformation time series with alert state"
  },
  {
    id: 5,
    title: "Roads & Isolation",
    description: "Blocked segments removed from graph, connected components recomputed.",
    details: [
      "OSM road network extracted via osmnx",
      "Blockage has three sources: predicted, reported, confirmed",
      "Blocked segments removed from graph",
      "Connected components recomputed",
      "For each settlement: component size, population, path to district headquarters",
      "No path to HQ = isolation score 1.0",
      "Blockage source shown (predicted vs reported vs confirmed)"
    ],
    input: ["OSM road network", "Blockage reports"],
    output: "Settlement isolation scores"
  },
  {
    id: 6,
    title: "Triage",
    description: "Weighted score with explicit isolation term.",
    details: [
      "Severity = 0.28·persons + 0.28·category + 0.22·area_risk + 0.12·wait + 0.10·isolation",
      "All five components stored individually",
      "If a household was reached late, district can see exactly why",
      "Weights are policy conversation, not hidden magic",
      "Isolation enters as its own term, not proxy for hazard exposure",
      "Request queue sorted by severity"
    ],
    input: ["Requests", "Area risk", "Isolation scores"],
    output: "Severity per request"
  },
  {
    id: 7,
    title: "Dispatch",
    description: "Requests partition into geographic zones, each becomes a QUBO, zones solve in parallel.",
    details: [
      "Geographic partitioning: ≤5 requests, ≤4 units per zone",
      "Each zone becomes a QUBO optimisation problem",
      "QUBO formulation: maximise severity assignment, minimise travel time",
      "Constraints: each request served at most once, each unit dispatched at most once",
      "Solver is runtime parameter: OR-Tools, simulated annealing, greedy, QAOA",
      "Fallback chain ends in dependency-free greedy heuristic",
      "Zones solved in parallel for horizontal scaling"
    ],
    input: ["Requests with severity", "Available units", "Travel costs"],
    output: "Unit-to-request assignments"
  },
  {
    id: 8,
    title: "The Loop Closes",
    description: "Citizen report of blocked road updates graph, which changes isolation, which changes severity.",
    details: [
      "Citizen submits report via PWA (offline-capable)",
      "Report queued and clustered with nearby reports",
      "Confirmed blockage updates road graph",
      "Graph changes connected components",
      "Isolation score recalculates for affected settlements",
      "Isolation changes severity",
      "Severity changes dispatch allocation",
      "That loop is the product"
    ],
    input: ["Citizen reports"],
    output: "Updated dispatch allocation"
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
      <h1 className="font-display font-semibold text-[18px] text-ink-000 mb-1">How a warning becomes a decision</h1>
      <p className="text-[13px] text-ink-200 mb-6 max-w-2xl">
        Eight stages from terrain to dispatch, with deformation measurement and isolation analysis as the headline differentiators.
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