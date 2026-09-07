"""One-off confidence check for the NER pivot Foundation sub-project:
does the carried terrain pipeline produce real derived rasters for the
Aizawl bbox? Not part of the ingest layer - docs/DATA.md's
ingest/terrain.py (a later sub-project) is the real, cached,
production version of this.

Run from services/api/: python scripts/verify_aizawl_pipeline.py
Requires data/raw/dem_aizawl.tif to already exist (see ingest/dem.py).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risk.terrain import compute_hand, compute_slope, compute_stream_distance, compute_twi

DEM_PATH = str(Path(__file__).resolve().parents[1] / "data" / "raw" / "dem_aizawl.tif")


def main() -> None:
    print(f"[verify] running terrain derivations against {DEM_PATH}")

    t0 = time.time()
    slope = compute_slope(DEM_PATH)
    print(f"[verify] slope: shape={slope.shape}, min={slope.min():.2f} deg, max={slope.max():.2f} deg ({time.time() - t0:.1f}s)")

    t0 = time.time()
    hand = compute_hand(DEM_PATH)
    valid_hand = hand[~__import__("numpy").isnan(hand)]
    print(f"[verify] HAND: shape={hand.shape}, min={valid_hand.min():.2f} m, max={valid_hand.max():.2f} m ({time.time() - t0:.1f}s)")

    t0 = time.time()
    twi = compute_twi(DEM_PATH)
    valid_twi = twi[__import__("numpy").isfinite(twi)]
    print(f"[verify] TWI: shape={twi.shape}, min={valid_twi.min():.2f}, max={valid_twi.max():.2f} ({time.time() - t0:.1f}s)")

    t0 = time.time()
    dist_stream = compute_stream_distance(DEM_PATH)
    valid_dist = dist_stream[~__import__("numpy").isnan(dist_stream)]
    print(f"[verify] dist_stream_m: shape={dist_stream.shape}, max={valid_dist.max():.1f} m ({time.time() - t0:.1f}s)")

    print("[verify] pipeline confirmed working on real Aizawl terrain.")


if __name__ == "__main__":
    main()
