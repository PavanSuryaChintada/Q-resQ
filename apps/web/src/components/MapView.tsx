import { Map as MapLibreMap, type GeoJSONSource, type StyleSpecification } from "maplibre-gl"
import { useEffect, useRef } from "react"
import type { RiskCellCollection, RequestOut, UnitOut } from "../lib/api"

const SEV_COLORS = ["#4A5D52", "#C9A227", "#D97B1F", "#C23B22", "#7A1E14"]

type FeatureCollection = {
  type: "FeatureCollection"
  features: Array<{
    type: "Feature"
    geometry: { type: "Point"; coordinates: [number, number] }
    properties: Record<string, unknown>
  }>
}

const EMPTY_FC: FeatureCollection = { type: "FeatureCollection", features: [] }

const BASEMAP_STYLE: StyleSpecification = {
  version: 8,
  glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#101A1E" } }],
}

interface Props {
  riskCells?: RiskCellCollection
  units?: UnitOut[]
  requests?: RequestOut[]
  center: [number, number]
  onSelectCell?: (id: number) => void
}

export function MapView({ riskCells, units, requests, center, onSelectCell }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const onSelectCellRef = useRef(onSelectCell)
  onSelectCellRef.current = onSelectCell

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

    map.on("load", () => {
      map.addSource("risk-cells", { type: "geojson", data: EMPTY_FC })
      map.addLayer({
        id: "risk-cells-fill",
        type: "circle",
        source: "risk-cells",
        paint: {
          "circle-radius": 10,
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
      map.addLayer({
        id: "units-points",
        type: "circle",
        source: "units",
        paint: {
          "circle-radius": 5,
          "circle-color": "#F0EBE1",
          "circle-stroke-width": 1,
          "circle-stroke-color": "#101A1E",
        },
      })

      map.addSource("requests", { type: "geojson", data: EMPTY_FC })
      map.addLayer({
        id: "requests-points",
        type: "circle",
        source: "requests",
        paint: {
          "circle-radius": 4,
          "circle-color": [
            "match",
            ["get", "status"],
            "open", "#C23B22",
            "assigned", "#C9A227",
            "#5C8A6E",
          ],
        },
      })
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
    if (!map || !requests) return
    const geojson: FeatureCollection = {
      type: "FeatureCollection",
      features: requests.map((r) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [r.location[1], r.location[0]] },
        properties: { status: r.status },
      })),
    }
    const setData = () => {
      const src = map.getSource<GeoJSONSource>("requests")
      src?.setData(geojson)
    }
    if (map.isStyleLoaded()) setData()
    else map.once("load", setData)
  }, [requests])

  return <div ref={containerRef} className="w-full h-full" />
}
