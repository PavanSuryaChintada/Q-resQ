import { Map as MapLibreMap, type GeoJSONSource, type StyleSpecification } from "maplibre-gl"
import { useEffect, useRef, useState } from "react"
import type { AssignmentOut, RiskCellCollection, RequestOut, UnitOut } from "../lib/api"

const SEV_COLORS = ["#4A5D52", "#C9A227", "#D97B1F", "#C23B22", "#7A1E14"]

type FeatureCollection = {
  type: "FeatureCollection"
  features: Array<{
    type: "Feature"
    geometry: { type: "Point" | "LineString"; coordinates: number[] | number[][] }
    properties: Record<string, unknown>
  }>
}

const EMPTY_FC: FeatureCollection = { type: "FeatureCollection", features: [] }

const BASEMAP_STYLE: StyleSpecification = {
  version: 8,
  glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
  sources: {
    "osm-tiles": {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [
    { id: "osm-tiles", type: "raster", source: "osm-tiles", minzoom: 0, maxzoom: 19 },
  ],
}

interface Props {
  riskCells?: RiskCellCollection
  units?: UnitOut[]
  requests?: RequestOut[]
  assignments?: AssignmentOut[]
  center: [number, number]
  onSelectCell?: (id: number) => void
  showRoutes?: boolean
  selectedRequestId?: string | null
}

/** True once addSource/addLayer for every layer this component owns
 * has actually run - not just once MapLibre's "load" event has fired.
 * Data-sync effects gate on THIS, not on map.isStyleLoaded(), so there
 * is no window where a fast-arriving query response calls setData()
 * before the source exists (setData on a missing source is a silent
 * no-op via optional chaining, which is exactly how markers/routes
 * were disappearing even though the API calls succeeded).
 */
export function MapView({
  riskCells, units, requests, assignments, center, onSelectCell,
  showRoutes = true, selectedRequestId,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const onSelectCellRef = useRef(onSelectCell)
  onSelectCellRef.current = onSelectCell
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = new MapLibreMap({
      container: containerRef.current,
      style: BASEMAP_STYLE,
      center: [center[1], center[0]],
      zoom: 11,
      attributionControl: false,
    })
    mapRef.current = map

    map.on("error", (e) => {
      // eslint-disable-next-line no-console
      console.error("[MapView] maplibre error:", e.error?.message ?? e)
    })

    const setup = () => {
      if (!map.getSource("risk-cells")) {
        map.addSource("risk-cells", { type: "geojson", data: EMPTY_FC })
        map.addLayer({
          id: "risk-cells-fill",
          type: "circle",
          source: "risk-cells",
          paint: {
            "circle-radius": 15,
            "circle-opacity": 0.55,
            "circle-color": [
              "match", ["get", "risk_band"],
              0, SEV_COLORS[0], 1, SEV_COLORS[1], 2, SEV_COLORS[2], 3, SEV_COLORS[3], 4, SEV_COLORS[4],
              "#34505C",
            ],
          },
        })
        map.on("mouseenter", "risk-cells-fill", () => { map.getCanvas().style.cursor = "pointer" })
        map.on("mouseleave", "risk-cells-fill", () => { map.getCanvas().style.cursor = "" })
        map.on("click", "risk-cells-fill", (e) => {
          const id = e.features?.[0]?.properties?.id
          if (typeof id === "number" && onSelectCellRef.current) onSelectCellRef.current(id)
        })
      }

      if (!map.getSource("routes")) {
        map.addSource("routes", { type: "geojson", data: EMPTY_FC })
        map.addLayer({
          id: "routes-lines",
          type: "line",
          source: "routes",
          layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": "#F0EBE1", "line-width": 4, "line-opacity": 0.9 },
        })
      }

      if (!map.getSource("units")) {
        map.addSource("units", { type: "geojson", data: EMPTY_FC })
        map.addLayer({
          id: "units-points",
          type: "circle",
          source: "units",
          paint: {
            "circle-radius": 8,
            "circle-color": "#F0EBE1",
            "circle-stroke-width": 2,
            "circle-stroke-color": "#101A1E",
          },
        })
      }

      if (!map.getSource("requests")) {
        map.addSource("requests", { type: "geojson", data: EMPTY_FC })
        map.addLayer({
          id: "requests-points",
          type: "circle",
          source: "requests",
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 0, 8, 10, 10, 15, 12],
            "circle-color": [
              "match", ["get", "severity_band"],
              0, SEV_COLORS[0], 1, SEV_COLORS[1], 2, SEV_COLORS[2], 3, SEV_COLORS[3], 4, SEV_COLORS[4],
              "#34505C",
            ],
          },
        })
        map.addLayer({
          id: "requests-ring",
          type: "circle",
          source: "requests",
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 0, 10, 10, 13, 15, 15],
            "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 0, 2, 10, 3, 15, 4],
            "circle-stroke-color": "#F0EBE1",
            "circle-stroke-opacity": ["match", ["get", "status"], "assigned", 1, "in_progress", 1, 0],
            "circle-color": "transparent",
          },
        })
      }

      setReady(true)
    }

    if (map.isStyleLoaded()) setup()
    else map.once("load", setup)

    return () => {
      map.remove()
      mapRef.current = null
      setReady(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !riskCells) return
    map.getSource<GeoJSONSource>("risk-cells")?.setData(riskCells as unknown as FeatureCollection)
  }, [ready, riskCells])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !units) return
    const geojson: FeatureCollection = {
      type: "FeatureCollection",
      features: units.map((u) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [u.position[1], u.position[0]] },
        properties: { label: u.label, status: u.status },
      })),
    }
    map.getSource<GeoJSONSource>("units")?.setData(geojson)
  }, [ready, units])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !requests) return
    const geojson: FeatureCollection = {
      type: "FeatureCollection",
      features: requests.map((r) => {
        const severityBand = r.severity != null && r.severity >= 0
          ? Math.min(Math.floor(r.severity * 5), 4)
          : 0
        return {
          type: "Feature",
          geometry: { type: "Point", coordinates: [r.location[1], r.location[0]] },
          properties: { status: r.status, severity_band: severityBand },
        }
      }),
    }
    map.getSource<GeoJSONSource>("requests")?.setData(geojson)
  }, [ready, requests])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !assignments || !units || !requests) return
    const features: FeatureCollection["features"] = assignments
      .map((assignment) => {
        const unit = units.find((u) => u.id === assignment.unit_id)
        const request = requests.find((r) => r.id === assignment.request_id)
        if (!unit || !request || !assignment.route) return null
        return {
          type: "Feature" as const,
          geometry: assignment.route,
          properties: { unit_id: assignment.unit_id, request_id: assignment.request_id },
        }
      })
      .filter((f): f is NonNullable<typeof f> => f !== null)
    map.getSource<GeoJSONSource>("routes")?.setData({ type: "FeatureCollection", features })
  }, [ready, assignments, units, requests])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !map.getLayer("routes-lines")) return
    map.setLayoutProperty("routes-lines", "visibility", showRoutes ? "visible" : "none")
  }, [ready, showRoutes])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !selectedRequestId || !requests) return
    const selected = requests.find((r) => r.id === selectedRequestId)
    if (!selected) return
    map.flyTo({ center: [selected.location[1], selected.location[0]], zoom: 14, duration: 1000 })
  }, [ready, selectedRequestId, requests])

  return <div ref={containerRef} className="w-full h-full" />
}
