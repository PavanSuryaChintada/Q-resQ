"""Solver benchmark endpoint. See docs/PRD.md F5, docs/TRD.md #6.

Wired to the real qubo_dispatch.benchmark() - honest results including
losses, same problem/lambda across every backend, never sorted or
filtered. See CLAUDE.md #2.1.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from qubo_dispatch import benchmark as qd_benchmark

from models import BenchmarkRow, BenchmarkRunRequest, BenchmarkRunResult
from routers.dispatch import build_current_problem

router = APIRouter()

_results: dict[UUID, list[BenchmarkRow]] = {}


@router.post("/run", response_model=BenchmarkRunResult)
def run_benchmark(payload: BenchmarkRunRequest) -> BenchmarkRunResult:
    problem = build_current_problem()
    backends = tuple(payload.backends) if payload.backends else ("qaoa", "annealing", "ortools", "greedy")

    raw_rows = qd_benchmark(problem, backends=backends)
    rows = [BenchmarkRow(**row) for row in raw_rows]

    round_id = uuid4()
    _results[round_id] = rows
    return BenchmarkRunResult(round_id=round_id, rows=rows)


@router.get("/results", response_model=list[BenchmarkRow])
def get_results(round_id: UUID) -> list[BenchmarkRow]:
    rows = _results.get(round_id)
    if rows is None:
        raise HTTPException(status_code=404, detail="benchmark round not found")
    return rows
