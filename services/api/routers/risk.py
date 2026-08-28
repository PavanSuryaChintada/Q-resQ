"""Risk grid endpoints. Fixtures for now - see BUILD_SPEC.md build order."""

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

router = APIRouter()

_FIXTURE_CELLS = [
    {"id": 1, "lon": 83.8945, "lat": 18.2949, "elevation_m": 4.2, "hand_m": 0.8,
     "slope_deg": 0.6, "twi": 9.1, "dist_stream_m": 120.0, "risk_score": 0.82, "risk_band": 4},
    {"id": 2, "lon": 83.9102, "lat": 18.3011, "elevation_m": 11.5, "hand_m": 6.3,
     "slope_deg": 2.1, "twi": 5.4, "dist_stream_m": 890.0, "risk_score": 0.31, "risk_band": 1},
]


@router.get("/cells", response_model=RiskCellCollection)
def list_cells(bbox: str | None = None, band_min: int | None = None) -> RiskCellCollection:
    cells = _FIXTURE_CELLS
    if band_min is not None:
        cells = [c for c in cells if c["risk_band"] >= band_min]
    features = [
        RiskCellFeature(
            geometry=GeoJSONGeometry(type="Point", coordinates=[c["lon"], c["lat"]]),
            properties=RiskCellProperties(
                id=c["id"], elevation_m=c["elevation_m"], hand_m=c["hand_m"],
                slope_deg=c["slope_deg"], twi=c["twi"], dist_stream_m=c["dist_stream_m"],
                risk_score=c["risk_score"], risk_band=c["risk_band"],
            ),
        )
        for c in cells
    ]
    return RiskCellCollection(features=features)


@router.get("/cell/{cell_id}", response_model=RiskCellDetail)
def cell_detail(cell_id: int) -> RiskCellDetail:
    cell = next((c for c in _FIXTURE_CELLS if c["id"] == cell_id), None)
    if cell is None:
        raise HTTPException(status_code=404, detail="risk cell not found")
    return RiskCellDetail(
        id=cell["id"],
        risk_score=cell["risk_score"],
        risk_band=cell["risk_band"],
        top_features=[
            FeatureContribution(name="hand_m", value=cell["hand_m"], contribution=0.40),
            FeatureContribution(name="rain_72h", value=64.0, contribution=0.30),
            FeatureContribution(name="slope_deg", value=cell["slope_deg"], contribution=0.15),
        ],
    )
