"""ESA WorldCover 10m via Planetary Computer. Clips to bbox, then
derives a forest-cover fraction raster at the region's risk grid
(services/api/config.py:REGION["grid_m"]) - vegetation root cohesion
matters for slope stability (docs/DATA.md #8, docs/TRAINING.md #2's
forest_frac feature).
"""

from __future__ import annotations

import argparse

import numpy as np
import planetary_computer
import pystac_client
import rasterio
import rioxarray
from rioxarray.merge import merge_arrays

from config import REGION
from ingest.config import BBOX, DATA_RAW_DIR, PLANETARY_COMPUTER_STAC_URL

LANDCOVER_OUTPUT = DATA_RAW_DIR / "landcover.tif"
FOREST_FRAC_OUTPUT = DATA_RAW_DIR / "forest_frac.tif"

TREE_COVER_CLASS = 10  # ESA WorldCover class code
RISK_GRID_CELL_M = float(REGION["grid_m"])
_METERS_PER_DEGREE_LAT = 111_320.0


def fetch_landcover(force: bool = False) -> None:
    if LANDCOVER_OUTPUT.exists() and not force:
        print(f"[landcover] {LANDCOVER_OUTPUT} already exists, skipping (use --force to refetch)")
        return

    print(f"[landcover] searching esa-worldcover for bbox {BBOX}")
    catalog = pystac_client.Client.open(PLANETARY_COMPUTER_STAC_URL, modifier=planetary_computer.sign_inplace)
    search = catalog.search(collections=["esa-worldcover"], bbox=BBOX)
    all_items = list(search.items())
    # the collection has both 2020 (v100) and 2021 (v200) tiles covering
    # the same footprints - keep only the more recent version, or
    # merge_arrays silently overlaps/duplicates data
    items = [item for item in all_items if "v200" in item.id]
    print(f"[landcover] found {len(all_items)} tile(s), using {len(items)} v200 (2021) tile(s)")
    if not items:
        print("[landcover] no tiles found for this bbox - stopping")
        return

    west, south, east, north = BBOX
    clipped_tiles = []
    for item in items:
        href = item.assets["map"].href
        print(f"[landcover]   opening {item.id}")
        # masked=True upcasts this categorical uint8 raster to
        # float32 (4x the memory) just to represent nodata as NaN -
        # this machine has only ~7.7GB RAM, keep it as uint8
        tile = rioxarray.open_rasterio(href, masked=False)
        try:
            clipped_tiles.append(tile.rio.clip_box(minx=west, miny=south, maxx=east, maxy=north))
        except Exception as exc:  # noqa: BLE001 - tile doesn't actually overlap the bbox
            print(f"[landcover]     {item.id} has no overlap with the bbox after clipping ({exc}), skipping")

    if not clipped_tiles:
        print("[landcover] no tile overlapped the bbox after clipping - stopping")
        return

    merged = merge_arrays(clipped_tiles) if len(clipped_tiles) > 1 else clipped_tiles[0]
    merged.rio.to_raster(LANDCOVER_OUTPUT, driver="COG")

    with rasterio.open(LANDCOVER_OUTPUT) as ds:
        print(f"[landcover] wrote {LANDCOVER_OUTPUT} shape={ds.shape} res={ds.res}")


def derive_forest_fraction(force: bool = False) -> None:
    if FOREST_FRAC_OUTPUT.exists() and not force:
        print(f"[landcover] {FOREST_FRAC_OUTPUT} already exists, skipping (use --force to refetch)")
        return
    if not LANDCOVER_OUTPUT.exists():
        print(f"[landcover] {LANDCOVER_OUTPUT} not found - run fetch_landcover first")
        return

    print(f"[landcover] deriving forest-cover fraction at the {int(RISK_GRID_CELL_M)}m risk grid")
    with rasterio.open(LANDCOVER_OUTPUT) as src:
        landcover = src.read(1)
        transform = src.transform
        crs = src.crs
        mean_lat = (src.bounds.top + src.bounds.bottom) / 2

    is_tree_cover = (landcover == TREE_COVER_CLASS).astype(np.float32)

    src_res_deg = abs(transform.a)
    meters_per_deg_lon = _METERS_PER_DEGREE_LAT * np.cos(np.radians(mean_lat))
    src_res_m = src_res_deg * meters_per_deg_lon
    block = max(1, round(RISK_GRID_CELL_M / src_res_m))

    n_rows_out = is_tree_cover.shape[0] // block
    n_cols_out = is_tree_cover.shape[1] // block
    trimmed = is_tree_cover[: n_rows_out * block, : n_cols_out * block]
    fraction = trimmed.reshape(n_rows_out, block, n_cols_out, block).mean(axis=(1, 3))

    out_transform = rasterio.Affine(
        transform.a * block, transform.b, transform.c,
        transform.d, transform.e * block, transform.f,
    )
    with rasterio.open(
        FOREST_FRAC_OUTPUT, "w", driver="GTiff",
        height=fraction.shape[0], width=fraction.shape[1], count=1,
        dtype="float32", crs=crs, transform=out_transform, nodata=-9999.0,
    ) as dst:
        dst.write(fraction.astype("float32"), 1)

    print(f"[landcover] wrote {FOREST_FRAC_OUTPUT} shape={fraction.shape} "
          f"mean forest_frac={fraction.mean():.4f}")


def fetch(force: bool = False) -> None:
    fetch_landcover(force=force)
    derive_forest_fraction(force=force)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    fetch(force=args.force)
