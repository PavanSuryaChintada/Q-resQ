"""Pydantic v2 request/response models. See BUILD_SPEC.md.

Shapes only, no behaviour - routers return real instances of these
(fixtures for now, real data later), so the frontend never has to
guess at the contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

RequestCategory = Literal["medical", "stranded", "evacuation"]
RequestStatus = Literal["open", "assigned", "in_progress", "resolved", "cancelled"]
UnitKind = Literal["boat", "ambulance", "truck", "team"]
UnitStatus = Literal["available", "assigned", "en_route", "returning", "offline"]
Backend = Literal["qaoa", "annealing", "ortools", "greedy"]
LogChannel = Literal["risk", "intake", "dispatch", "road", "system"]


# --- risk -------------------------------------------------------------

class RiskCellProperties(BaseModel):
    id: int
    elevation_m: float | None = None
    hand_m: float | None = None
    slope_deg: float | None = None
    twi: float | None = None
    dist_stream_m: float | None = None
    risk_score: float | None = None
    risk_band: int | None = None


class GeoJSONGeometry(BaseModel):
    type: Literal["Point", "Polygon"]
    coordinates: list


class RiskCellFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONGeometry
    properties: RiskCellProperties


class RiskCellCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[RiskCellFeature]


class FeatureContribution(BaseModel):
    name: str
    value: float
    contribution: float


class RiskCellDetail(BaseModel):
    id: int
    risk_score: float
    risk_band: int
    top_features: list[FeatureContribution]


# --- requests -----------------------------------------------------------

class RequestCreate(BaseModel):
    id: UUID
    location: tuple[float, float]  # (lat, lon)
    people_count: int
    category: RequestCategory
    note: str | None = None
    created_at: datetime


class RequestOut(RequestCreate):
    status: RequestStatus
    severity: float | None = None
    sev_people: float | None = None
    sev_category: float | None = None
    sev_area_risk: float | None = None
    sev_wait: float | None = None
    synced_at: datetime | None = None
    resolved_at: datetime | None = None


class RequestPatch(BaseModel):
    status: RequestStatus


# --- units ---------------------------------------------------------------

class UnitOut(BaseModel):
    id: UUID
    label: str
    kind: UnitKind
    capacity: int
    position: tuple[float, float]
    status: UnitStatus
    updated_at: datetime


class UnitPatch(BaseModel):
    status: UnitStatus | None = None
    position: tuple[float, float] | None = None


# --- dispatch --------------------------------------------------------------

class DispatchSolveRequest(BaseModel):
    backend: Backend = "qaoa"
    timeout_s: float = 10.0


class AssignmentOut(BaseModel):
    id: UUID
    unit_id: UUID
    request_id: UUID
    zone_id: int | None = None
    travel_s: int | None = None
    route: dict | None = None  # GeoJSON LineString for unit->request path


class DispatchRoundOut(BaseModel):
    id: UUID
    started_at: datetime
    zone_count: int | None = None
    request_count: int | None = None
    unit_count: int | None = None
    backend: Backend | None = None
    fell_back: bool = False
    objective: float | None = None
    solve_ms: int | None = None
    assignments: list[AssignmentOut] = []


# --- benchmark ---------------------------------------------------------------

class BenchmarkRow(BaseModel):
    backend: str
    objective: float | None = None
    solve_ms: int | None = None
    constraints_valid: bool | None = None
    qubit_count: int | None = None
    notes: str | None = None


class BenchmarkRunRequest(BaseModel):
    backends: list[Backend] | None = None  # None = all four, per docs/TRD.md #6


class BenchmarkRunResult(BaseModel):
    round_id: UUID
    rows: list[BenchmarkRow]


# --- log -----------------------------------------------------------------------

class LogLine(BaseModel):
    id: int
    at: datetime
    channel: LogChannel
    severity: int
    message: str


# --- seed ------------------------------------------------------------------------

class SeedResult(BaseModel):
    status: Literal["seeded"]
    units_created: int
    requests_created: int
