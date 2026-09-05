"""Risk grid endpoints. Wired to real computed risk (risk/features.py:
real Srikakulam DEM + real IMD rainfall + the heuristic formula) - not
a fixture. See BUILD_SPEC.md.

No LightGBM model or SAR labels yet - this is the heuristic path.
"""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException

from models import (
    FeatureContribution,
    GeoJSONGeometry,
    LiveRiskOut,
    LiveRiskRangeOut,
    RiskCellCollection,
    RiskCellDetail,
    RiskCellFeature,
    RiskCellProperties,
)
from risk.features import DEMO_BBOX
from risk.features import build_risk_cells
from risk.heuristic import DISASTER_WEIGHTS, band, compute_heuristic_risk
from risk.rainfall import fetch_live_rain_72h, live_rain_date_range, today_iso

router = APIRouter()

_cells_by_type: dict[str, list[dict]] = {}
_DEMO_CENTER_LON = (DEMO_BBOX[0] + DEMO_BBOX[2]) / 2
_DEMO_CENTER_LAT = (DEMO_BBOX[1] + DEMO_BBOX[3]) / 2


def _get_cells(disaster_type: str = "cyclone") -> list[dict]:
    if disaster_type not in DISASTER_WEIGHTS:
        raise HTTPException(
            status_code=422, detail=f"unknown disaster_type {disaster_type!r}, expected one of {list(DISASTER_WEIGHTS)}"
        )
    if disaster_type not in _cells_by_type:
        _cells_by_type[disaster_type] = build_risk_cells(disaster_type=disaster_type)
    return _cells_by_type[disaster_type]


@router.get("/cells", response_model=RiskCellCollection)
def list_cells(band_min: int | None = None, disaster_type: str = "cyclone") -> RiskCellCollection:
    cells = _get_cells(disaster_type)
    if band_min is not None:
        cells = [c for c in cells if c["risk_band"] >= band_min]
    features = [
        RiskCellFeature(
            geometry=GeoJSONGeometry(type="Point", coordinates=[c["lon"], c["lat"]]),
            properties=RiskCellProperties(
                id=c["id"], hand_m=c["hand_m"], slope_deg=c["slope_deg"],
                dist_stream_m=c["dist_stream_m"], risk_score=c["risk_score"], risk_band=c["risk_band"],
            ),
        )
        for c in cells
    ]
    return RiskCellCollection(features=features)


@router.get("/live/range", response_model=LiveRiskRangeOut)
def live_risk_range() -> LiveRiskRangeOut:
    try:
        min_date, max_date = live_rain_date_range(_DEMO_CENTER_LAT, _DEMO_CENTER_LON)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"live rainfall range unavailable: {exc}") from exc
    return LiveRiskRangeOut(min_date=min_date, max_date=max_date)


@router.get("/live", response_model=LiveRiskOut)
def live_risk(date: str | None = None, disaster_type: str = "cyclone") -> LiveRiskOut:
    """Today's (or any nearby date's) flood risk, computed from the same
    terrain grid as the Titli scenario but with real live/forecast
    rainfall from Open-Meteo instead of the fixed 2018 IMD data. One
    rainfall reading for the demo area's centre is applied uniformly
    across all cells - real terrain variation still drives the map,
    but this is not a per-cell live interpolation, which is disclosed
    in the response's `note` field rather than left implicit.
    """
    if disaster_type not in DISASTER_WEIGHTS:
        raise HTTPException(
            status_code=422, detail=f"unknown disaster_type {disaster_type!r}, expected one of {list(DISASTER_WEIGHTS)}"
        )
    target_date = date or today_iso()
    try:
        rain_72h = fetch_live_rain_72h(_DEMO_CENTER_LAT, _DEMO_CENTER_LON, target_date)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"live rainfall unavailable for {target_date}: {exc}"
        ) from exc

    cells = _get_cells(disaster_type)
    hand_vals = np.array([c["hand_m"] for c in cells])
    slope_vals = np.array([c["slope_deg"] for c in cells])
    stream_vals = np.array([c["dist_stream_m"] for c in cells])
    drainage_vals = np.full(len(cells), 0.5)
    rain_vals = np.full(len(cells), rain_72h)

    risk_score, _ = compute_heuristic_risk(
        hand_vals, rain_vals, slope_vals, stream_vals, drainage_vals,
        weights=DISASTER_WEIGHTS[disaster_type],
    )
    bands = [band(float(s)) for s in risk_score]
    max_band = max(bands) if bands else 0
    elevated = sum(1 for b in bands if b >= 2)

    verdict = (
        "no significant flood risk expected"
        if max_band <= 1
        else f"elevated risk in {elevated} of {len(cells)} area cells - monitor conditions"
    )

    return LiveRiskOut(
        date=target_date,
        rain_72h_mm=rain_72h,
        max_band=max_band,
        elevated_cell_count=elevated,
        total_cells=len(cells),
        verdict=verdict,
        note=(
            "Terrain is the same computed DEM/HAND grid as the Titli scenario. "
            "Rainfall is one live reading for the demo area's centre from "
            "Open-Meteo, applied uniformly - not interpolated per cell."
        ),
    )


@router.get("/cell/{cell_id}", response_model=RiskCellDetail)
def cell_detail(cell_id: int, disaster_type: str = "cyclone") -> RiskCellDetail:
    cells = _get_cells(disaster_type)
    cell = next((c for c in cells if c["id"] == cell_id), None)
    if cell is None:
        raise HTTPException(status_code=404, detail="risk cell not found")

    contributions = sorted(cell["contributions"].items(), key=lambda kv: kv[1], reverse=True)[:3]
    raw_values = {"hand": cell["hand_m"], "rain_72h": cell["rain_72h_mm"],
                  "slope": cell["slope_deg"], "dist_stream": cell["dist_stream_m"], "drainage": 0.5}
    return RiskCellDetail(
        id=cell["id"],
        risk_score=cell["risk_score"],
        risk_band=cell["risk_band"],
        top_features=[
            FeatureContribution(name=name, value=raw_values.get(name, 0.0), contribution=contribution)
            for name, contribution in contributions
        ],
    )
