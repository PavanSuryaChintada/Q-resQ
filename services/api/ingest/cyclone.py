"""IBTrACS North Indian Ocean track data, NOAA NCEI. Filtered to
Cyclone Titli, 2018 season. Idempotent.
"""

from __future__ import annotations

import argparse
import io

import pandas as pd
import requests

from ingest.config import DATA_RAW_DIR

IBTRACS_NI_URL = "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.NI.list.v04r01.csv"
OUTPUT_PATH = DATA_RAW_DIR / "titli_track.csv"


def fetch(force: bool = False) -> None:
    if OUTPUT_PATH.exists() and not force:
        print(f"[cyclone] {OUTPUT_PATH} already exists, skipping (use --force to refetch)")
        return

    print(f"[cyclone] downloading IBTrACS North Indian Ocean CSV from {IBTRACS_NI_URL}")
    response = requests.get(IBTRACS_NI_URL, timeout=120)
    response.raise_for_status()
    print(f"[cyclone] downloaded {len(response.content) / 1e6:.1f} MB")

    # IBTrACS CSVs have a units row right after the header - skip it
    raw = pd.read_csv(io.StringIO(response.text), header=0, skiprows=[1], low_memory=False)

    titli = raw[(raw["NAME"].str.strip() == "TITLI") & (raw["SEASON"] == 2018)].copy()
    print(f"[cyclone] found {len(titli)} track rows for TITLI 2018")
    if titli.empty:
        print("[cyclone] no rows matched NAME == 'TITLI' and SEASON == 2018 - stopping")
        return

    keep_cols = [c for c in ["ISO_TIME", "LAT", "LON", "USA_WIND", "USA_PRES", "WMO_WIND", "WMO_PRES"] if c in titli.columns]
    out = titli[keep_cols].rename(columns={
        "ISO_TIME": "timestamp", "LAT": "lat", "LON": "lon",
        "USA_WIND": "max_wind_kt", "USA_PRES": "min_pressure_mb",
    })
    out.to_csv(OUTPUT_PATH, index=False)
    print(f"[cyclone] wrote {len(out)} rows to {OUTPUT_PATH}")

    print("[cyclone] rows adjacent to the known landfall window (~04:30-05:30 IST, 11 Oct 2018 = ~23:00-00:00 UTC, 10-11 Oct):")
    out["timestamp"] = pd.to_datetime(out["timestamp"])
    landfall_window = out[(out["timestamp"] >= "2018-10-10T18:00:00") & (out["timestamp"] <= "2018-10-11T12:00:00")]
    print(landfall_window.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    fetch(force=args.force)
