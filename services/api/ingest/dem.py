"""Copernicus DEM GLO-30 via Microsoft Planetary Computer STAC.

Idempotent: skips if data/raw/dem_srikakulam.tif already exists,
unless --force. No API key needed.
"""

from __future__ import annotations

import argparse
import sys

import planetary_computer
import pystac_client
import rasterio
import rioxarray
from rioxarray.merge import merge_arrays

from ingest.config import BBOX, DATA_RAW_DIR, PLANETARY_COMPUTER_STAC_URL

OUTPUT_PATH = DATA_RAW_DIR / "dem_srikakulam.tif"


def fetch(force: bool = False) -> None:
    if OUTPUT_PATH.exists() and not force:
        print(f"[dem] {OUTPUT_PATH} already exists, skipping (use --force to refetch)")
        return

    print(f"[dem] searching cop-dem-glo-30 for bbox {BBOX}")
    catalog = pystac_client.Client.open(PLANETARY_COMPUTER_STAC_URL, modifier=planetary_computer.sign_inplace)
    search = catalog.search(collections=["cop-dem-glo-30"], bbox=BBOX)
    items = list(search.items())
    print(f"[dem] found {len(items)} tile(s)")
    if not items:
        print("[dem] no tiles found for this bbox - stopping")
        sys.exit(1)

    tiles = []
    for item in items:
        href = item.assets["data"].href
        print(f"[dem]   opening {item.id}")
        tiles.append(rioxarray.open_rasterio(href, masked=True))

    print("[dem] merging tiles")
    merged = merge_arrays(tiles) if len(tiles) > 1 else tiles[0]

    print("[dem] clipping to bbox")
    west, south, east, north = BBOX
    clipped = merged.rio.clip_box(minx=west, miny=south, maxx=east, maxy=north)

    print(f"[dem] writing {OUTPUT_PATH}")
    clipped.rio.to_raster(OUTPUT_PATH, driver="COG")

    with rasterio.open(OUTPUT_PATH) as ds:
        arr = ds.read(1, masked=True)
        print(f"[dem] shape={ds.shape} res={ds.res} elevation min={arr.min()} max={arr.max()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    fetch(force=args.force)
