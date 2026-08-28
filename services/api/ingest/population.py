"""WorldPop constrained 100m population for India, clipped to bbox.

Optional per the spec: if the direct download is awkward or the URL
doesn't resolve, report it and skip rather than fabricate an
alternate endpoint.
"""

from __future__ import annotations

import argparse

import rasterio
import rioxarray
import requests

from ingest.config import BBOX, DATA_RAW_DIR

OUTPUT_PATH = DATA_RAW_DIR / "population.tif"

# WorldPop constrained, UN-adjusted, 100m, India, 2020
WORLDPOP_URL = (
    "https://data.worldpop.org/GIS/Population/"
    "Global_2000_2020_Constrained/2020/BSGM/IND/ind_ppp_2020_constrained.tif"
)


def fetch(force: bool = False) -> None:
    if OUTPUT_PATH.exists() and not force:
        print(f"[population] {OUTPUT_PATH} already exists, skipping (use --force to refetch)")
        return

    print(f"[population] checking WorldPop URL: {WORLDPOP_URL}")
    try:
        head = requests.head(WORLDPOP_URL, timeout=30, allow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[population] URL not reachable ({exc}) - this source is optional, skipping.")
        return

    if head.status_code != 200:
        print(f"[population] URL returned status {head.status_code}, not 200 - "
              f"not guessing an alternate endpoint. This source is optional, skipping.")
        return

    size_mb = int(head.headers.get("Content-Length", 0)) / 1e6
    print(f"[population] URL resolves, {size_mb:.0f} MB (whole-India raster)")

    print("[population] trying streamed range-request clip (no bbox-subset API on this server)")
    try:
        da = rioxarray.open_rasterio(WORLDPOP_URL, masked=True)
    except rasterio.errors.RasterioIOError as exc:
        print(f"[population] streaming failed: {exc}")
        print(f"[population] this server doesn't support HTTP range requests, so the only way "
              f"to clip a small district out of this is to download the full {size_mb:.0f} MB "
              f"India-wide raster first. That's the 'awkward' case - skipping by default. "
              f"Source is confirmed real and reachable: {WORLDPOP_URL}")
        return

    west, south, east, north = BBOX
    clipped = da.rio.clip_box(minx=west, miny=south, maxx=east, maxy=north)
    clipped.rio.to_raster(OUTPUT_PATH, driver="COG")

    with rasterio.open(OUTPUT_PATH) as ds:
        arr = ds.read(1, masked=True)
        print(f"[population] wrote {OUTPUT_PATH} shape={ds.shape} total population~={arr.sum():.0f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    fetch(force=args.force)
