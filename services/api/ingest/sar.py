"""Sentinel-1 RTC via Planetary Computer, for flood labels.

If nothing covers the bbox/date window, say so plainly and stop - do
not substitute a different date range or sensor.
"""

from __future__ import annotations

import argparse
import json

import planetary_computer
import pystac_client
import requests

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
    for item in items:
        orbit = item.properties.get("sat:orbit_state", "unknown")
        dt = item.datetime.isoformat() if item.datetime else "unknown"
        print(f"[sar]   {item.id}  orbit={orbit}  datetime={dt}")
        manifest.append({"id": item.id, "orbit_state": orbit, "datetime": dt, "assets": list(item.assets.keys())})

        for asset_key, asset in item.assets.items():
            if asset_key not in ("vh", "vv"):
                continue
            out_path = SAR_DIR / f"{item.id}_{asset_key}.tif"
            if out_path.exists() and not force:
                print(f"[sar]     {out_path.name} already exists, skipping")
                continue
            print(f"[sar]     downloading {asset_key} -> {out_path.name}")
            response = requests.get(asset.href, timeout=300)
            response.raise_for_status()
            out_path.write_bytes(response.content)

    manifest_path = SAR_DIR / "scenes_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"[sar] wrote scene manifest to {manifest_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    fetch(force=args.force)
