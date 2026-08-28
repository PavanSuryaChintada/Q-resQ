import { useState } from "react"
import { ArchitecturePage } from "./components/ArchitecturePage"
import { DispatchControls } from "./components/DispatchControls"
import { DispatchLedger } from "./components/DispatchLedger"
import { Header } from "./components/Header"
import { LayersPanel } from "./components/LayersPanel"
import { MapView } from "./components/MapView"
import { RequestsPanel } from "./components/RequestsPanel"
import { RiskCellPanel } from "./components/RiskCellPanel"
import { UnitsPanel } from "./components/UnitsPanel"
import { useRequests, useRiskCells, useUnits } from "./lib/hooks"

const DEMO_CENTER: [number, number] = [18.325, 83.9]

export default function App() {
  const [view, setView] = useState<"dashboard" | "architecture">("dashboard")
  const [selectedCellId, setSelectedCellId] = useState<number | null>(null)
  const { data: riskCells } = useRiskCells()
  const { data: units } = useUnits()
  const { data: requests } = useRequests()

  return (
    <div className="h-screen w-screen flex flex-col bg-ground-000 overflow-hidden">
      <Header view={view} onViewChange={setView} />
      {view === "architecture" ? (
        <ArchitecturePage />
      ) : (
        <div className="flex-1 flex min-h-0">
          <div className="w-[240px] shrink-0 border-r border-ground-300 bg-ground-100 flex flex-col">
            <LayersPanel />
            <RiskCellPanel cellId={selectedCellId} />
            <UnitsPanel />
          </div>
          <div className="flex-1 flex flex-col min-w-0">
            <div className="flex-1 min-h-0">
              <MapView
                riskCells={riskCells}
                units={units}
                requests={requests}
                center={DEMO_CENTER}
                onSelectCell={setSelectedCellId}
              />
            </div>
            <DispatchControls />
            <div className="h-[220px] shrink-0 flex flex-col">
              <RequestsPanel center={DEMO_CENTER} />
            </div>
          </div>
          <DispatchLedger />
        </div>
      )}
    </div>
  )
}
