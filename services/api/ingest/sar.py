"""Sentinel-1 RTC via Planetary Computer, for flood labels.

If nothing covers the bbox/date window, say so plainly and stop - do
not substitute a different date range or sensor.

Each scene asset is a full, uncropped ~1.85GB Cloud-Optimized GeoTIFF
(a full ~250km swath) - downloading whole files reliably overwhelmed
this machine's ~7.7GB RAM and disk headroom. These are COGs, so
rasterio can windowed-read just our small district bbox directly off
the remote URL via HTTP range requests (same pattern as
ingest/dem.py) - a few MB instead of a few GB per file.
"""

from __future__ import annotations

import argparse
import json

import planetary_computer
import pystac_client
import rasterio
import rasterio.warp
import rasterio.windows

from ingest.config import BBOX, DATA_RAW_DIR, PLANETARY_COMPUTER_STAC_URL

SAR_DIR = DATA_RAW_DIR / "sar"
SAR_START = "2018-10-11"
SAR_END = "2018-10-20"


def fetch(force: bool = False) -> None:
    SAR_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[sar] searching sentinel-1-rtc for bbox {BBOX}, {SAR_START} to {SAR_END} (both orbit directions)")
    catalog = pystac_client.Client.open(PLANETARY_COMPUTER_STAC_URL, modifier=planetary_computer.sign_inplace)
    search = catalog.search(collections=["sentinel-1-rtc"], bbox=BBOX, datetime=f"{SAR_START}/{SAR_END}")
    items = list(search.items())

    if not items:
        print(f"[sar] NO Sentinel-1 RTC scenes found for bbox {BBOX} in {SAR_START}..{SAR_END}.")
        print("[sar] not substituting a different date range or sensor - stopping.")
        return

    print(f"[sar] found {len(items)} scene(s):")
    manifest = []
    west, south, east, north = BBOX
    for item in items:
        orbit = item.properties.get("sat:orbit_state", "unknown")
        dt = item.datetime.isoformat() if item.datetime else "unknown"
        print(f"[sar]   {item.id}  orbit={orbit}  datetime={dt}")
        manifest.append({"id": item.id, "orbit_state": orbit, "datetime": dt, "assets": list(item.assets.keys())})

        for asset_key, asset in item.assets.items():
            if asset_key not in ("vh", "vv"):
                continue
            out_path = SAR_DIR / f"{item.id}_{asset_key}_srikakulam.tif"
            if out_path.exists() and not force:
                print(f"[sar]     {out_path.name} already exists, skipping")
                continue
            print(f"[sar]     windowed-reading {asset_key} for the district bbox (COG range request, not a full download)")
            with rasterio.open(asset.href) as src:
                # Sentinel-1 RTC assets are in the scene's native UTM
                # zone (e.g. EPSG:32645), not EPSG:4326 like the DEM -
                # reproject the bbox into the source CRS before
                # windowing, or from_bounds silently computes a
                # degenerate window and "no overlap" even when the
                # STAC search matched this scene
                src_west, src_south, src_east, src_north = rasterio.warp.transform_bounds(
                    "EPSG:4326", src.crs, west, south, east, north)
                window = rasterio.windows.from_bounds(src_west, src_south, src_east, src_north, src.transform)
                window = window.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
                if window.width <= 0 or window.height <= 0:
                    print(f"[sar]       no overlap with the bbox, skipping")
                    continue
                data = src.read(1, window=window)
                transform = src.window_transform(window)
                profile = src.profile.copy()
            profile.update(height=data.shape[0], width=data.shape[1], transform=transform, driver="GTiff")
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(data, 1)
            print(f"[sar]       wrote {out_path.name}, shape={data.shape}, "
                  f"{out_path.stat().st_size / 1e6:.2f} MB (vs ~1.85GB for the full scene)")

    manifest_path = SAR_DIR / "scenes_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"[sar] wrote scene manifest to {manifest_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    fetch(force=args.force)
