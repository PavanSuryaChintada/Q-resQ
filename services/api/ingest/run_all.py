"""Runs ingest scripts 1-6 in order, then the optional population
step (non-fatal), then generates the manifest. Prints a summary
table of what was fetched, file sizes, and anything that failed.
"""

from __future__ import annotations

import argparse
import time
import traceback

from ingest import cyclone, dem, landcover, manifest, osm, population, rainfall, sar
from ingest.config import DATA_RAW_DIR

STEPS = [
    ("dem", dem.fetch),
    ("osm", osm.fetch),
    ("rainfall", rainfall.fetch),
    ("cyclone", cyclone.fetch),
    ("landcover", landcover.fetch),
    ("sar", sar.fetch),
]

OPTIONAL_STEPS = [
    ("population", population.fetch),
]


def _run_step(name: str, fn, force: bool, optional: bool) -> tuple[str, str, float, str | None]:
    print(f"\n=== running {name}{' (optional)' if optional else ''} ===")
    start = time.monotonic()
    try:
        fn(force=force)
        status = "ok"
        error = None
    except Exception as exc:  # noqa: BLE001 - keep going through the remaining steps
        status = "skipped (optional)" if optional else "FAILED"
        error = f"{type(exc).__name__}: {exc}"
        print(f"[run_all] {name} {'failed (non-fatal)' if optional else 'FAILED'}: {error}")
        if not optional:
            traceback.print_exc()
    elapsed = time.monotonic() - start
    return name, status, elapsed, error


def run(force: bool = False) -> None:
    results = [_run_step(name, fn, force, optional=False) for name, fn in STEPS]
    results += [_run_step(name, fn, force, optional=True) for name, fn in OPTIONAL_STEPS]

    print("\n" + "=" * 72)
    print(f"{'step':<12} {'status':<20} {'time_s':>8}")
    print("-" * 72)
    for name, status, elapsed, error in results:
        print(f"{name:<12} {status:<20} {elapsed:>8.1f}")
        if error:
            print(f"    {error}")

    print("\nfiles in data/raw:")
    total_mb = 0.0
    for path in sorted(DATA_RAW_DIR.rglob("*")):
        if path.is_file():
            size_mb = path.stat().st_size / 1e6
            total_mb += size_mb
            print(f"  {path.relative_to(DATA_RAW_DIR)}  {size_mb:.2f} MB")
    print(f"total: {total_mb:.1f} MB")

    manifest.generate()

    failed = [name for name, status, _, _ in results if status == "FAILED"]
    if failed:
        print(f"\nFAILED steps: {', '.join(failed)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run(force=args.force)
