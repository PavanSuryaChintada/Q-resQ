"""Generates data/raw/MANIFEST.md: source, licence, and fetch date for
every file actually present - for attribution in the deck.
"""

from __future__ import annotations

import datetime

from ingest.config import DATA_RAW_DIR

SOURCES = {
    "dem_srikakulam.tif": (
        "Copernicus DEM GLO-30, via Microsoft Planetary Computer STAC (cop-dem-glo-30)",
        "https://planetarycomputer.microsoft.com/dataset/cop-dem-glo-30",
        "CC-BY 4.0 (Copernicus Programme)",
    ),
    "facilities.geojson": (
        "OpenStreetMap, via Overpass API / osmnx",
        "https://www.openstreetmap.org/copyright",
        "ODbL 1.0",
    ),
    "roads.geojson": (
        "OpenStreetMap, via Overpass API / osmnx",
        "https://www.openstreetmap.org/copyright",
        "ODbL 1.0",
    ),
    "waterways.geojson": (
        "OpenStreetMap, via Overpass API / osmnx",
        "https://www.openstreetmap.org/copyright",
        "ODbL 1.0",
    ),
    "rainfall_openmeteo_2018.parquet": (
        "Open-Meteo Historical Weather API (ERA5 reanalysis)",
        "https://open-meteo.com/en/docs/historical-weather-api",
        "CC-BY 4.0",
    ),
    "rainfall_nasapower_2018.parquet": (
        "NASA POWER (PRECTOTCORR, daily point)",
        "https://power.larc.nasa.gov/",
        "Public domain (NASA)",
    ),
    "titli_track.csv": (
        "IBTrACS v04r01, North Indian Ocean basin",
        "https://www.ncei.noaa.gov/products/international-best-track-archive",
        "Public domain (NOAA NCEI)",
    ),
    "landcover.tif": (
        "ESA WorldCover 10m, via Microsoft Planetary Computer STAC",
        "https://planetarycomputer.microsoft.com/dataset/esa-worldcover",
        "CC-BY 4.0",
    ),
    "imperviousness.tif": (
        "Derived from landcover.tif (built-up class fraction at the 250m risk grid)",
        "n/a (derived)",
        "Same as landcover.tif: CC-BY 4.0",
    ),
    "population.tif": (
        "WorldPop constrained, UN-adjusted, India, 100m, 2020",
        "https://www.worldpop.org/",
        "CC-BY 4.0",
    ),
    "srikakulam_dem.tif": (
        "Copernicus DEM GLO-30, via OpenTopography Global DEM API",
        "https://portal.opentopography.org/raster?opentopoID=OTSDEM.032021.4326.3",
        "CC-BY 4.0 (Copernicus Programme) - earlier fetch, superseded by dem_srikakulam.tif",
    ),
}

SAR_SOURCE = (
    "Sentinel-1 RTC (Copernicus), via Microsoft Planetary Computer STAC",
    "https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc",
    "CC-BY 4.0 (contains modified Copernicus Sentinel data)",
)


def generate() -> None:
    lines = [
        "# Data manifest",
        "",
        f"Generated {datetime.date.today().isoformat()}. Region: Srikakulam district "
        "bbox (west=83.30 south=18.00 east=84.55 north=19.25), see ingest/config.py.",
        "",
        "| File | Source | Licence | Fetched | Size |",
        "|---|---|---|---|---|",
    ]

    for filename, (source, url, license_) in SOURCES.items():
        path = DATA_RAW_DIR / filename
        if not path.exists():
            continue
        fetched = datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()
        size_mb = path.stat().st_size / 1e6
        lines.append(f"| `{filename}` | [{source}]({url}) | {license_} | {fetched} | {size_mb:.2f} MB |")

    sar_dir = DATA_RAW_DIR / "sar"
    if sar_dir.exists():
        for path in sorted(sar_dir.glob("*.tif")):
            fetched = datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()
            size_mb = path.stat().st_size / 1e6
            source, url, license_ = SAR_SOURCE
            lines.append(f"| `sar/{path.name}` | [{source}]({url}) | {license_} | {fetched} | {size_mb:.2f} MB |")

    manifest_path = DATA_RAW_DIR / "MANIFEST.md"
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[manifest] wrote {manifest_path}")


if __name__ == "__main__":
    generate()
