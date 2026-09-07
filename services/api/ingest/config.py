"""Shared config for the ingest layer. Import BBOX from here - never
hardcode it in an individual script.

BBOX is derived from services/api/config.py:REGION - the single region
constant every module imports - not redefined here.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

INGEST_DIR = Path(__file__).resolve().parent
API_DIR = INGEST_DIR.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from config import REGION  # noqa: E402

# (west, south, east, north) in EPSG:4326 degrees - Aizawl district, Mizoram
_bbox = REGION["bbox"]
BBOX = (_bbox["west"], _bbox["south"], _bbox["east"], _bbox["north"])

DATA_RAW_DIR = API_DIR / "data" / "raw"
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

PLANETARY_COMPUTER_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)
