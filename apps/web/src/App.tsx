import { useState } from "react"
import { ArchitecturePage } from "./components/ArchitecturePage"
import { DemoGuide } from "./components/DemoGuide"
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
  const [showGuide, setShowGuide] = useState(false)
  const { data: riskCells } = useRiskCells()
  const { data: units } = useUnits()
  const { data: requests } = useRequests()
  const { data: assignments } = useAssignments()

  return (
    <div className="h-screen w-screen flex flex-col bg-ground-000 overflow-hidden">
      <Header
        view={view}
        onViewChange={setView}
        guideOpen={showGuide}
        onToggleGuide={() => setShowGuide((v) => !v)}
      />
      {view === "architecture" ? (
        <ArchitecturePage />
      ) : view === "flow" ? (
        <FlowPage />
      ) : (
        <div className="flex-1 flex min-h-0">
          <div className="w-[240px] shrink-0 border-r border-ground-300 bg-ground-100 flex flex-col overflow-y-auto">
            <LayersPanel />
            <RiskCellPanel cellId={selectedCellId} />
            <UnitsPanel />
          </div>
          <div className="flex-1 flex flex-col min-w-0">
            <div className="flex-1 min-h-0 relative">
              {showGuide && <DemoGuide onClose={() => setShowGuide(false)} />}
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
            <div className="h-[240px] shrink-0 flex flex-col border-t border-ground-300">
              {useCarousel ? (
                <RequestCarousel
                  requests={requests || []}
                  onRequestSelect={setSelectedRequestId}
                  selectedRequestId={selectedRequestId}
                  onSwitchView={() => setUseCarousel(false)}
                />
              ) : (
                <RequestsPanel
                  center={DEMO_CENTER}
                  onSwitchView={() => setUseCarousel(true)}
                  onRequestSelect={setSelectedRequestId}
                  selectedRequestId={selectedRequestId}
                />
              )}
            </div>
          </div>
          <DispatchLedger />
        </div>
      )}
    </div>
  )
}
