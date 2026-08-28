import { useState } from "react"
import { ArchitecturePage } from "./components/ArchitecturePage"
import { DispatchControls } from "./components/DispatchControls"
import { DispatchLedger } from "./components/DispatchLedger"
import { FlowPage } from "./components/FlowPage"
import { Header } from "./components/Header"
import { LayersPanel } from "./components/LayersPanel"
import { MapView } from "./components/MapView"
import { RequestCarousel } from "./components/RequestCarousel"
import { RequestsPanel } from "./components/RequestsPanel"
import { RiskCellPanel } from "./components/RiskCellPanel"
import { UnitsPanel } from "./components/UnitsPanel"
import { useAssignments, useRequests, useRiskCells, useUnits } from "./lib/hooks"

const DEMO_CENTER: [number, number] = [18.325, 83.9]

export default function App() {
  const [view, setView] = useState<"dashboard" | "architecture" | "flow">("dashboard")
  const [selectedCellId, setSelectedCellId] = useState<number | null>(null)
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null)
  const [showRoutes, setShowRoutes] = useState(true)
  const [useCarousel, setUseCarousel] = useState(false)
  const { data: riskCells } = useRiskCells()
  const { data: units } = useUnits()
  const { data: requests } = useRequests()
  const { data: assignments } = useAssignments()

  // Debug logging
  console.log("App render - Data loading status:", {
    riskCellsLoaded: !!riskCells,
    riskCellsCount: riskCells?.features?.length || 0,
    unitsLoaded: !!units,
    unitsCount: units?.length || 0,
    requestsLoaded: !!requests,
    requestsCount: requests?.length || 0,
    assignmentsLoaded: !!assignments,
    assignmentsCount: assignments?.length || 0,
  })

  return (
    <div className="h-screen w-screen flex flex-col bg-ground-000 overflow-hidden">
      <Header view={view} onViewChange={setView} />
      {view === "architecture" ? (
        <ArchitecturePage />
      ) : view === "flow" ? (
        <FlowPage />
      ) : (
        <div className="flex-1 flex min-h-0">
          <div className="w-[240px] shrink-0 border-r border-ground-300 bg-ground-100 flex flex-col">
            <LayersPanel />
            <RiskCellPanel cellId={selectedCellId} />
            <UnitsPanel />
          </div>
          <div className="flex-1 flex flex-col min-w-0">
            {/* Debug status bar */}
            <div className="h-6 border-b border-ground-300 bg-ground-200 flex items-center px-3 gap-4 text-[10px] font-data">
              <span className={riskCells ? "text-ink-000" : "text-ink-300"}>
                Risk: {riskCells?.features?.length || 0} cells
              </span>
              <span className={units ? "text-ink-000" : "text-ink-300"}>
                Units: {units?.length || 0}
              </span>
              <span className={requests ? "text-ink-000" : "text-ink-300"}>
                Requests: {requests?.length || 0}
              </span>
              <span className={assignments ? "text-ink-000" : "text-ink-300"}>
                Assignments: {assignments?.length || 0}
              </span>
            </div>
            <div className="flex-1 min-h-0">
              <MapView
                riskCells={riskCells}
                units={units}
                requests={requests}
                assignments={assignments}
                center={DEMO_CENTER}
                onSelectCell={setSelectedCellId}
                showRoutes={showRoutes}
                selectedRequestId={selectedRequestId}
              />
            </div>
            <DispatchControls showRoutes={showRoutes} onToggleRoutes={() => setShowRoutes(!showRoutes)} />
            <div className="h-[220px] shrink-0 flex flex-col">
              {useCarousel ? (
                <div className="flex-1 overflow-hidden">
                  <div className="h-8 flex items-center px-3 bg-ground-200 border-b border-ground-300">
                    <span className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200">
                      Request Queue
                    </span>
                    <button
                      onClick={() => setUseCarousel(false)}
                      className="ml-auto h-6 px-2 bg-ground-300 border border-ground-400 text-ink-000 text-[11px] font-display uppercase tracking-wide hover:bg-ground-400"
                    >
                      List View
                    </button>
                  </div>
                  <div className="p-3 h-full overflow-y-auto">
                    <RequestCarousel 
                      requests={requests || []} 
                      onRequestSelect={setSelectedRequestId}
                      selectedRequestId={selectedRequestId}
                    />
                  </div>
                </div>
              ) : (
                <>
                  <div className="h-8 flex items-center px-3 bg-ground-200 border-b border-ground-300">
                    <span className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200">
                      Request Queue
                    </span>
                    <button
                      onClick={() => setUseCarousel(true)}
                      className="ml-auto h-6 px-2 bg-ground-300 border border-ground-400 text-ink-000 text-[11px] font-display uppercase tracking-wide hover:bg-ground-400"
                    >
                      Carousel View
                    </button>
                  </div>
                  <RequestsPanel center={DEMO_CENTER} />
                </>
              )}
            </div>
          </div>
          <DispatchLedger />
        </div>
      )}
    </div>
  )
}
