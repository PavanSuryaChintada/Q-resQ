import { useState } from "react"
import { ArchitecturePage } from "./components/ArchitecturePage"
import { DemoGuide } from "./components/DemoGuide"
import { DispatchControls } from "./components/DispatchControls"
import { DispatchLedger } from "./components/DispatchLedger"
import { FlowPage } from "./components/FlowPage"
import { Header } from "./components/Header"
import { IsolationControl } from "./components/IsolationControl"
import { LayersPanel } from "./components/LayersPanel"
import { MapView } from "./components/MapView"
import { RequestCarousel } from "./components/RequestCarousel"
import { RequestsPanel } from "./components/RequestsPanel"
import { ReportsPanel } from "./components/ReportsPanel"
import { RiskCellPanel } from "./components/RiskCellPanel"
import { SolutionSummaryPage } from "./components/SolutionSummaryPage"
import { UnitsPanel } from "./components/UnitsPanel"
import {
  useAssignments, useBlockDemoTrigger, useClearRoadSegment, useIsolation,
  useReports, useRequests, useRiskCells, useUnits,
} from "./lib/hooks"
import type { RoadGeometry } from "./lib/api"

// Aizawl district HQ - see services/api/config.py:REGION["hq"]
const DEMO_CENTER: [number, number] = [23.7271, 92.7176]

export default function App() {
  const [view, setView] = useState<"dashboard" | "architecture" | "flow" | "summary">("dashboard")
  const [selectedCellId, setSelectedCellId] = useState<number | null>(null)
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null)
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null)
  const [showRoutes, setShowRoutes] = useState(true)
  const [useCarousel, setUseCarousel] = useState(false)
  const [showGuide, setShowGuide] = useState(false)
  const [showReports, setShowReports] = useState(false)
  const [blockedSegmentId, setBlockedSegmentId] = useState<number | null>(null)
  const [blockedRoadGeom, setBlockedRoadGeom] = useState<RoadGeometry | null>(null)
  const [dispatchFlow, setDispatchFlow] = useState<{ settlement: string; status: string } | null>(null)
  const { data: riskCells } = useRiskCells()
  const { data: units } = useUnits()
  const { data: requests } = useRequests()
  const { data: assignments } = useAssignments()
  const { data: reports } = useReports()
  const { data: isolation } = useIsolation()
  const blockDemoTrigger = useBlockDemoTrigger()
  const clearRoadSegment = useClearRoadSegment()

  const isolatedSettlements = (isolation ?? []).filter((s) => s.isolated)
  const isBlocked = blockedSegmentId !== null

  const handleBlockNH6 = async () => {
    const result = await blockDemoTrigger.mutateAsync()
    setBlockedSegmentId(result.segment_id)
    setBlockedRoadGeom(result.geom)
  }

  const handleClearNH6 = async () => {
    if (blockedSegmentId !== null) {
      await clearRoadSegment.mutateAsync(blockedSegmentId)
    }
    setBlockedSegmentId(null)
    setBlockedRoadGeom(null)
  }

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
      ) : view === "summary" ? (
        <SolutionSummaryPage />
      ) : (
        <div className="flex-1 flex min-h-0 relative">
          <div className="w-[240px] shrink-0 border-r border-ground-300 bg-ground-100 flex flex-col overflow-y-auto">
            <div className="h-8 flex items-center px-3 bg-ground-300 border-b border-ground-400 shrink-0">
              <span className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-000">
                Situational awareness
              </span>
            </div>
            <LayersPanel />
            <RiskCellPanel cellId={selectedCellId} />
            <UnitsPanel />
            <IsolationControl
              onBlockNH6={handleBlockNH6}
              onClearNH6={handleClearNH6}
              isolatedSettlements={isolatedSettlements.map((s) => s.name)}
              isBlocked={isBlocked}
              onTriggerAlert={(settlement) => {
                setDispatchFlow({ settlement, status: "alerting" })
              }}
            />
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
                selectedReportId={selectedReportId}
                reports={showReports ? reports : undefined}
                blockedRoadGeom={blockedRoadGeom}
                isolatedSettlements={isolatedSettlements.map((s) => ({
                  name: s.name, lon: s.lon ?? 0, lat: s.lat ?? 0,
                }))}
              />
            </div>
            <DispatchControls
              showRoutes={showRoutes}
              onToggleRoutes={() => setShowRoutes(!showRoutes)}
            />
            <div className="h-8 flex items-center px-3 bg-ground-200 border-t border-ground-300">
              <button
                onClick={() => setShowReports(false)}
                className={`px-3 py-1 text-[11px] font-display uppercase tracking-wide ${
                  !showReports ? "bg-ground-300" : "bg-ground-100"
                }`}
              >
                Emergency Requests
              </button>
              <button
                onClick={() => setShowReports(true)}
                className={`px-3 py-1 text-[11px] font-display uppercase tracking-wide ${
                  showReports ? "bg-ground-300" : "bg-ground-100"
                }`}
              >
                Citizen Reports
              </button>
            </div>
            <div className="h-[240px] shrink-0 flex flex-col border-t border-ground-300">
              {showReports ? (
                <ReportsPanel
                  onReportSelect={setSelectedReportId}
                  selectedReportId={selectedReportId}
                />
              ) : useCarousel ? (
                <RequestCarousel
                  requests={requests || []}
                  units={units || []}
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

          {dispatchFlow && (
            <div className="absolute top-0 right-0 bottom-0 w-96 z-20 border-l border-ground-300 bg-ground-000 flex flex-col">
              <div className="h-8 shrink-0 flex items-center justify-between px-3 bg-ground-200 border-b border-ground-300">
                <span className="font-display font-semibold text-[11px] uppercase tracking-[0.12em] text-ink-200">
                  Dispatch flow · {dispatchFlow.settlement}
                </span>
                <button
                  onClick={() => setDispatchFlow(null)}
                  className="text-ink-300 text-[11px] font-display uppercase tracking-wide hover:text-ink-000"
                >
                  Close
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-3 space-y-3">
                <div className="p-3 border border-ground-300 bg-ground-100">
                  <div className="text-[11px] text-ink-200 mb-1">Alert status</div>
                  <div className="text-[12px] text-ink-000 font-body">
                    {dispatchFlow.status === "alerting" ? "Triggering CAP alert..." : "Dispatch in progress"}
                  </div>
                </div>

                <div className="p-3 border border-ground-300 bg-ground-100">
                  <div className="text-[11px] text-ink-200 mb-1">Settlement</div>
                  <div className="text-[12px] text-ink-000 font-body">{dispatchFlow.settlement}</div>
                  <div className="font-data text-[11px] text-ink-300 mt-1">23.73, 92.72</div>
                </div>

                <div className="p-3 border border-ground-300 bg-ground-100">
                  <div className="text-[11px] text-ink-200 mb-1">Assigned resources</div>
                  <div className="space-y-1.5">
                    <div className="flex justify-between items-center">
                      <span className="text-[12px] text-ink-000">Rescue team</span>
                      <span className="text-[11px] text-state-ok font-data">Dispatched</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[12px] text-ink-000">Truck</span>
                      <span className="text-[11px] text-state-ok font-data">Dispatched</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[12px] text-ink-000">Medical</span>
                      <span className="text-[11px] text-state-warn font-data">Standby</span>
                    </div>
                  </div>
                </div>

                <div className="p-3 border border-ground-300 bg-ground-100">
                  <div className="text-[11px] text-ink-200 mb-1">Road route</div>
                  <div className="text-[12px] text-ink-000">NH6 → Tlawng Road → Settlement</div>
                  <div className="font-data text-[11px] text-ink-300 mt-1">12.4 km · ETA 35 min</div>
                </div>

                <div className="p-3 border-l-2 border-l-sev-3 border-t border-r border-b border-ground-300 bg-ground-100">
                  <div className="text-[11px] text-ink-200 mb-1">Isolation status</div>
                  <div className="text-[12px] text-sev-3">Critical — no alternate route</div>
                  <div className="text-[11px] text-ink-300 mt-1">Only road: NH6 (blocked)</div>
                </div>

                <button
                  onClick={() => setDispatchFlow({ ...dispatchFlow, status: "dispatched" })}
                  className="w-full h-8 border border-ground-400 bg-ground-300 text-ink-000 text-[12px] font-display uppercase tracking-wide hover:bg-ground-400"
                >
                  Approve dispatch
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
