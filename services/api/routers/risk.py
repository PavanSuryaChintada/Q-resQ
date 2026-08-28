"""Risk grid endpoints. Wired to real computed risk (risk/features.py:
real Srikakulam DEM + real IMD rainfall + the heuristic formula) - not
a fixture. See BUILD_SPEC.md.

No LightGBM model or SAR labels yet - this is the heuristic path.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models import (
    FeatureContribution,
    GeoJSONGeometry,
    RiskCellCollection,
    RiskCellDetail,
    RiskCellFeature,
    RiskCellProperties,
)
from risk.features import build_risk_cells

router = APIRouter()

_cells: list[dict] | None = None


def _get_cells() -> list[dict]:
    global _cells
    if _cells is None:
        _cells = build_risk_cells()
    return _cells


@router.get("/cells", response_model=RiskCellCollection)
def list_cells(band_min: int | None = None) -> RiskCellCollection:
    cells = _get_cells()
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


@router.get("/cell/{cell_id}", response_model=RiskCellDetail)
def cell_detail(cell_id: int) -> RiskCellDetail:
    cells = _get_cells()
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
