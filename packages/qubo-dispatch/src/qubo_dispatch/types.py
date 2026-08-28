"""Data shapes for qubo-dispatch. See BUILD_SPEC.md §1."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Unit:
    id: str
    capacity: int
    position: tuple[float, float]  # (lat, lon)
    kind: str = "boat"


@dataclass(frozen=True)
class Request:
    id: str
    severity: float  # 0..1, computed upstream
    people: int
    position: tuple[float, float]


@dataclass
class DispatchProblem:
    units: list[Unit]
    requests: list[Request]
    travel_time_s: dict[tuple[str, str], float]  # (unit_id, request_id) -> seconds
    alpha: float = 0.3  # travel-vs-severity tradeoff


@dataclass
class QUBO:
    Q: dict[tuple[int, int], float]  # upper-triangular sparse
    n_vars: int
    index: dict[tuple[str, str], int]  # (unit_id, request_id) -> variable index
    reverse: dict[int, tuple[str, str]]
    offset: float = 0.0
    lam: float = 0.0  # the tuned penalty, kept for reporting


@dataclass
class DispatchResult:
    assignments: list[tuple[str, str]]  # (unit_id, request_id)
    objective: float
    backend: str
    fell_back: bool
    solve_ms: int
    qubit_count: int | None = None
