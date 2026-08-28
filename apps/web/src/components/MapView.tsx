import { Map as MapLibreMap, type GeoJSONSource, type StyleSpecification } from "maplibre-gl"
import { useEffect, useRef } from "react"
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
    {
      id: "osm-tiles",
      type: "raster",
      source: "osm-tiles",
      minzoom: 0,
      maxzoom: 19,
    },
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

export function MapView({ riskCells, units, requests, assignments, center, onSelectCell, showRoutes = true, selectedRequestId }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const onSelectCellRef = useRef(onSelectCell)
  onSelectCellRef.current = onSelectCell

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    console.log("Initializing map with center:", center)
    const map = new MapLibreMap({
      container: containerRef.current,
      style: BASEMAP_STYLE,
      center: [center[1], center[0]],
      zoom: 11,
      attributionControl: false,
    })
    mapRef.current = map
    console.log("Map initialized successfully")

    map.on("load", () => {
      console.log("Map loaded, adding layers")
      
      map.addSource("risk-cells", { type: "geojson", data: EMPTY_FC })
      console.log("Added risk-cells source")
      
      map.addLayer({
        id: "risk-cells-fill",
        type: "circle",
        source: "risk-cells",
        minzoom: 0,
        maxzoom: 22,
        paint: {
          "circle-radius": 15,
          "circle-opacity": 0.55,
          "circle-color": [
            "match",
            ["get", "risk_band"],
            0, SEV_COLORS[0],
            1, SEV_COLORS[1],
            2, SEV_COLORS[2],
            3, SEV_COLORS[3],
            4, SEV_COLORS[4],
            "#34505C",
          ],
        },
      })
      console.log("Added risk-cells-fill layer")
      map.on("mouseenter", "risk-cells-fill", () => {
        map.getCanvas().style.cursor = "pointer"
      })
      map.on("mouseleave", "risk-cells-fill", () => {
        map.getCanvas().style.cursor = ""
      })
      map.on("click", "risk-cells-fill", (e) => {
        const feature = e.features?.[0]
        const id = feature?.properties?.id
        if (typeof id === "number" && onSelectCellRef.current) onSelectCellRef.current(id)
      })

      map.addSource("units", { type: "geojson", data: EMPTY_FC })
      console.log("Added units source")
      
      map.addLayer({
        id: "units-points",
        type: "circle",
        source: "units",
        minzoom: 0,
        maxzoom: 22,
        paint: {
          "circle-radius": 8,
          "circle-color": "#F0EBE1",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#101A1E",
        },
      })
      console.log("Added units-points layer")

      map.addSource("requests", { type: "geojson", data: EMPTY_FC })
      console.log("Added requests source")
      
      // Inner circle - severity-based color
      map.addLayer({
        id: "requests-points",
        type: "circle",
        source: "requests",
        minzoom: 0,
        maxzoom: 22,
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            0, 8,
            10, 10,
            15, 12,
          ],
          "circle-color": [
            "match",
            ["get", "severity_band"],
            0, SEV_COLORS[0],
            1, SEV_COLORS[1],
            2, SEV_COLORS[2],
            3, SEV_COLORS[3],
            4, SEV_COLORS[4],
            "#34505C",
          ],
        },
      })
      console.log("Added requests-points layer")
      
      // Outer ring - shows assignment status (white ring for assigned requests)
      map.addLayer({
        id: "requests-ring",
        type: "circle",
        source: "requests",
        minzoom: 0,
        maxzoom: 22,
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            0, 10,
            10, 13,
            15, 15,
          ],
          "circle-stroke-width": [
            "interpolate",
            ["linear"],
            ["zoom"],
            0, 2,
            10, 3,
            15, 4,
          ],
          "circle-stroke-color": "#F0EBE1",
          "circle-stroke-opacity": [
            "match",
            ["get", "status"],
            "assigned", 1,
            "in_progress", 1,
            0,
          ],
          "circle-color": "transparent",
        },
      })
      console.log("Added requests-ring layer")

      // Routes layer for unit-to-request paths
      map.addSource("routes", { type: "geojson", data: EMPTY_FC })
      console.log("Added routes source")
      
      map.addLayer({
        id: "routes-lines",
        type: "line",
        source: "routes",
        minzoom: 0,
        maxzoom: 22,
        layout: {
          "line-cap": "round",
          "line-join": "round",
        },
        paint: {
          "line-color": "#F0EBE1",
          "line-width": 4,
          "line-opacity": 0.9,
        },
      })
      console.log("Added routes-lines layer")
    })

    return () => {
      map.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !riskCells) return
    const setData = () => {
      const src = map.getSource<GeoJSONSource>("risk-cells")
      src?.setData(riskCells as unknown as FeatureCollection)
    }
    if (map.isStyleLoaded()) setData()
    else map.once("load", setData)
  }, [riskCells])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !units) return
    const geojson: FeatureCollection = {
      type: "FeatureCollection",
      features: units.map((u) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [u.position[1], u.position[0]] },
        properties: { label: u.label, status: u.status },
      })),
    }
    const setData = () => {
      const src = map.getSource<GeoJSONSource>("units")
      src?.setData(geojson)
    }
    if (map.isStyleLoaded()) setData()
    else map.once("load", setData)
  }, [units])

  useEffect(() => {
    const map = mapRef.current
    console.log("Requests effect triggered:", { map: !!map, requestsCount: requests?.length })
    
    if (!map || !requests) {
      console.log("Skipping requests - missing data")
      return
    }
    
    const geojson: FeatureCollection = {
      type: "FeatureCollection",
      features: requests.map((r) => {
        // Convert severity to band (0-4) for map display
        // Severity can range from 0 to ~1.0 (sum of weighted components)
        // We normalize it to bands: 0-0.2->0, 0.2-0.4->1, 0.4-0.6->2, 0.6-0.8->3, 0.8+->4
        let severityBand = 0
        if (r.severity != null && r.severity >= 0) {
          severityBand = Math.min(Math.floor(r.severity * 5), 4)
        }
        console.log(`Request ${r.id}: severity=${r.severity}, band=${severityBand}, color=${SEV_COLORS[severityBand]}, location=${r.location}`)
        return {
          type: "Feature",
          geometry: { type: "Point", coordinates: [r.location[1], r.location[0]] },
          properties: { 
            status: r.status,
            severity_band: severityBand,
          },
        }
      }),
    }
    console.log("Setting request data with", geojson.features.length, "features")
    const setData = () => {
      const src = map.getSource<GeoJSONSource>("requests")
      if (src) {
        console.log("Setting request source data")
        src.setData(geojson)
      } else {
        console.log("Request source not found!")
      }
    }
    if (map.isStyleLoaded()) setData()
    else map.once("load", setData)
  }, [requests])

  useEffect(() => {
    const map = mapRef.current
    console.log("Routes effect triggered:", { 
      map: !!map, 
      assignmentsCount: assignments?.length, 
      unitsCount: units?.length, 
      requestsCount: requests?.length 
    })
    
    if (!map || !assignments || !units || !requests) {
      console.log("Skipping routes - missing data")
      return
    }
    
    const routeFeatures: FeatureCollection["features"] = assignments
      .map((assignment) => {
        const unit = units.find((u) => u.id === assignment.unit_id)
        const request = requests.find((r) => r.id === assignment.request_id)
        if (!unit || !request || !assignment.route) {
          console.log("Skipping assignment - missing data:", { 
            assignmentId: assignment.id, 
            hasUnit: !!unit, 
            hasRequest: !!request, 
            hasRoute: !!assignment.route 
          })
          return null
        }
        
        console.log("Adding route for assignment:", assignment.id)
        return {
          type: "Feature" as const,
          geometry: assignment.route,
          properties: {
            unit_id: assignment.unit_id,
            request_id: assignment.request_id,
          },
        }
      })
      .filter((f): f is NonNullable<typeof f> => f !== null)
    
    const geojson: FeatureCollection = {
      type: "FeatureCollection",
      features: routeFeatures,
    }
    
    console.log("Setting route data with", routeFeatures.length, "features")
    const setData = () => {
      const src = map.getSource<GeoJSONSource>("routes")
      if (src) {
        console.log("Setting route source data")
        src.setData(geojson)
      } else {
        console.log("Route source not found!")
      }
    }
    if (map.isStyleLoaded()) setData()
    else map.once("load", setData)
  }, [assignments, units, requests])

  useEffect(() => {
    const map = mapRef.current
    console.log("Route visibility effect triggered:", { map: !!map, showRoutes })
    
    if (!map) return
    
    const setVisibility = () => {
      if (map.getLayer("routes-lines")) {
        console.log("Setting route visibility to:", showRoutes ? "visible" : "none")
        map.setLayoutProperty("routes-lines", "visibility", showRoutes ? "visible" : "none")
      } else {
        console.log("routes-lines layer not found!")
      }
    }
    
    if (map.isStyleLoaded()) setVisibility()
    else map.once("load", setVisibility)
  }, [showRoutes])

  useEffect(() => {
    const map = mapRef.current
    console.log("MapView navigation effect triggered:", { map: !!map, selectedRequestId, requestsCount: requests?.length })
    
    if (!map || !selectedRequestId || !requests) {
      console.log("Skipping navigation - missing data")
      return
    }
    
    const selectedRequest = requests.find(r => r.id === selectedRequestId)
    if (!selectedRequest) {
      console.log("Request not found:", selectedRequestId)
      return
    }
    
    console.log("Navigating to request:", selectedRequest.id, "at", selectedRequest.location)
    
    // Force a small delay to ensure map is ready
    setTimeout(() => {
      if (!mapRef.current) return
      
      const moveToRequest = () => {
        console.log("Executing flyTo to:", [selectedRequest.location[1], selectedRequest.location[0]])
        mapRef.current!.flyTo({
          center: [selectedRequest.location[1], selectedRequest.location[0]],
          zoom: 14,
          duration: 1000
        })
      }
      
      if (mapRef.current.isStyleLoaded()) {
        console.log("Map style loaded, moving immediately")
        moveToRequest()
      } else {
        console.log("Map style not loaded, waiting for load event")
        mapRef.current.once("load", moveToRequest)
      }
    }, 100)
  }, [selectedRequestId, requests])

  return <div ref={containerRef} className="w-full h-full" />
}
