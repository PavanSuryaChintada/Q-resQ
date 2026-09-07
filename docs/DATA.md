# DATA — Q-ResQ NER

Region: **Aizawl district, Mizoram**
bbox: `west=92.55  south=23.55  east=93.05  north=24.05`

Two parts: a prompt for Claude Code covering everything scriptable, and a short manual list.

**Start the Sentinel-1 SLC download on day 1.** It is tens of gigabytes and it is the only item that cannot be rushed later — and it requires a human to register an Earthdata account, so it cannot be done from an agent session alone.

---

## Part 1 — Prompt for Claude Code

Paste everything between the rules into a fresh session at the repo root.

---

> Build the NER data ingest layer under `services/api/ingest/`. One script per source, each independently runnable, each caching to `data/raw/` and skipping existing files unless `--force`. Do not build application features — ingest scripts only.
>
> **Region:** Aizawl district, Mizoram. bbox `west=92.55 south=23.55 east=93.05 north=24.05`. This lives in `services/api/config.py` as a single constant every script imports. Never hardcode it twice.
>
> **Environment check first.** Verify these import in this environment before writing anything: `pystac-client`, `planetary-computer`, `rasterio`, `richdem`, `pysheds`, `geopandas`, `osmnx`, `xarray`, `requests`, `pandas`. `rasterio`/GDAL is the likely failure. If pip fails, tell me immediately — do not work around it. Report back before script 1.
>
> Then write these in order:
>
> **1. `ingest/dem.py`** — Copernicus DEM GLO-30 via Planetary Computer STAC (`https://planetarycomputer.microsoft.com/api/stac/v1`, collection `cop-dem-glo-30`). Search bbox, sign with `planetary_computer.sign`, mosaic, clip, write `data/raw/dem_aizawl.tif` as COG in EPSG:4326. Print shape, resolution, elevation min/max. No key needed.
>
> **2. `ingest/terrain.py`** — derive from the DEM at 100 m grid resolution and write each as a GeoTIFF to `data/raw/terrain/`:
> - slope (degrees)
> - aspect — **write `aspect_sin.tif` and `aspect_cos.tif`, not raw degrees.** Aspect is circular; raw degrees would teach a model that 359° and 1° are maximally different.
> - plan curvature, profile curvature
> - LS factor
> - HAND (via pysheds: fill → flow direction → accumulation → stream threshold → height above nearest drainage)
> - TWI = ln(upslope_area / tan(slope))
>
> Cache every intermediate. Flow accumulation is slow and you will re-run this.
>
> **3. `ingest/osm.py`** — Overpass, three outputs:
> - `data/raw/roads.geojson` — drivable network via `osmnx.graph_from_bbox(network_type="drive")`, edges with highway, maxspeed, length
> - `data/raw/settlements.geojson` — `place` in village, hamlet, town, suburb, neighbourhood; keep name and population where tagged
> - `data/raw/facilities.geojson` — `amenity` in hospital, clinic, school, fire_station, police, community_centre; plus `emergency=*`
>
> Also `data/raw/waterways.geojson` — waterway in river, stream. Rate-limit politely, retry on 429.
>
> **4. `ingest/road_cut.py`** — derive `dist_road_m` (Euclidean distance from each grid cell to the nearest road centreline) and `is_cut_slope` (`dist_road_m < 50 AND slope_deg > 25`). Write both as GeoTIFFs. This encodes the "unplanned hill cutting" driver named in the problem statement, so get it right and print the fraction of the district it flags.
>
> **5. `ingest/landslides.py`** — NASA Global Landslide Catalog (`https://catalog.data.gov/dataset/global-landslide-catalog-export`). Filter to the bbox with generous padding — the catalogue is sparse, so pad to the whole of Mizoram and neighbouring districts to get usable label counts. Write `data/raw/landslides.geojson` with date, location, trigger, size, fatalities where present. **Print the count inside the strict bbox and inside the padded region separately** — I need to know how few labels we actually have locally.
>
> **6. `ingest/rainfall.py`** — Open-Meteo archive (`https://archive-api.open-meteo.com/v1/archive`) hourly precipitation over a 0.05° grid across the bbox, for the last three monsoon seasons. Derive antecedent windows: 1 d, 3 d, 7 d, 15 d accumulation and max hourly intensity. Write `data/raw/rainfall_antecedent.parquet`. Parameterise dates — this must also serve live forecast mode later.
>
> **7. `ingest/soil_moisture.py`** — NASA SMAP L3 soil moisture, or ERA5-Land volumetric soil water if SMAP is awkward. Clip to bbox, write `data/raw/soil_moisture.nc`. Coarse resolution is expected and fine — say what it is in the manifest.
>
> **8. `ingest/landcover.py`** — ESA WorldCover 10 m via Planetary Computer (collection `esa-worldcover`). Clip, write `data/raw/landcover.tif`, plus a forest-cover fraction raster resampled to the 100 m grid. Vegetation root cohesion matters for slope stability.
>
> **9. `ingest/run_all.py`** — runs 1-8 in order, prints a summary table of files, sizes, and failures.
>
> **Rules:**
> - Idempotent. Re-running skips existing unless `--force`.
> - Never fabricate a URL. If a source is unreachable from this environment, report it and stop — do not substitute a different source, region, or date range without telling me.
> - Print progress. These are slow.
> - No authentication in this set. If a source demands a key, stop and tell me.
> - Write `data/raw/MANIFEST.md` — each file, source URL, licence, resolution, fetch date. Needed for the attribution slide.
>
> Start with the environment check and report back before writing script 1.

---

## Part 2 — Manual, and one of them is urgent

### A · Sentinel-1 SLC — DO THIS ON DAY 1

`https://search.asf.alaska.edu/` (Alaska Satellite Facility Vertex)

1. Free Earthdata account — register now, approval is instant
2. Search: Sentinel-1, **SLC** product (not GRD — GRD has no phase information and InSAR is impossible without it)
3. Filter to the Aizawl bbox, **single track, single orbit direction** (all ascending or all descending, never mixed)
4. Select at least 20 acquisitions spanning a monsoon season
5. Queue the download and leave it running

**This is tens of gigabytes and it is the critical path for the entire InSAR feature.** Everything else in this document can be fetched in an afternoon. This cannot.

If bandwidth makes 20 scenes impossible, take 6 — a short SBAS stack still produces a real velocity field, just with wider error bars. Say what the stack size was.

### B · GSI landslide inventory and lithology

`https://bhukosh.gsi.gov.in/` — free registration, usually instant

1. Map viewer → layers → **Landslide Inventory** and **Landslide Susceptibility (NLSM 1:50,000)**
2. Zoom to Mizoram, export as shapefile
3. Also export the **geology / lithology** layer for the district
4. Save to `data/raw/manual/gsi/`

GSI's inventory holds roughly 91,000 landslide records with about 33,904 field-validated, and the NLSM programme covers landslide-prone terrain at 1:50,000 across nineteen states. **This is a far better label source than the NASA catalogue** — get it if you can.

**Timebox to 30 minutes.** If the portal fights you, proceed on the NASA catalogue and note the reduced label count. Do not lose half a day here.

### C · IMD rainfall API

`https://mausam.imd.gov.in/` · `https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html`

The problem statement names IMD integration explicitly, so having it matters more for this PS than for the last one. If the live API needs credentials you cannot get in time, ingest the IMD gridded historical NetCDF and say: *"IMD gridded product ingested; live API integration is a credentials step, and the adapter is written against their published schema."*

### D · Mizoram state disaster data

`https://dmr.mizoram.gov.in/` — Mizoram DM&R Department

Historical landslide records, vulnerable-location lists, and shelter registries. Optional, but state-sourced data plays well with a ministry panel. Timebox to 20 minutes.

---

## 3. Order of operations

**Right now, before anything else:** register the Earthdata account and start the SLC download.

**Then:** run the ingest for scripts 1-4. Terrain is the foundation and everything else waits on it.

**In background:** GSI (30 min cap), Mizoram DM&R (20 min cap).

**Skip unless there is spare time:** IMD gridded historical, DM&R shelter registry.

---

## 4. Attribution

Keep `MANIFEST.md` current. Free does not mean unattributed, and a licence slide is a cheap credibility win with a government panel.

- Copernicus DEM — © DLR e.V. 2010-2014, © Airbus Defence and Space GmbH
- Sentinel-1 — Copernicus Sentinel data, processed by ESA
- ESA WorldCover — © ESA WorldCover project
- OpenStreetMap — © OpenStreetMap contributors, ODbL
- NASA Global Landslide Catalog — NASA Goddard Space Flight Center
- SMAP — NASA National Snow and Ice Data Center DAAC
- GSI Bhukosh — Geological Survey of India
- IMD — India Meteorological Department
