"""Shared config for the ingest layer. Import BBOX from here - never
hardcode it in an individual script.
"""

from __future__ import annotations

import os
from pathlib import Path

# Srikakulam district, Andhra Pradesh
# (west, south, east, north) in EPSG:4326 degrees
BBOX = (83.30, 18.00, 84.55, 19.25)

INGEST_DIR = Path(__file__).resolve().parent
API_DIR = INGEST_DIR.parent
DATA_RAW_DIR = API_DIR / "data" / "raw"

DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

PLANETARY_COMPUTER_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

# Cyclone Titli: landfall roughly 04:30-05:30 IST, 11 Oct 2018, near
# Palasa/Vajrapukotturu mandal, Srikakulam district - see docs/PRD.md #5
TITLI_LANDFALL_DATE = "2018-10-11"
DEFAULT_EVENT_START = "2018-10-01"
DEFAULT_EVENT_END = "2018-10-20"


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)
