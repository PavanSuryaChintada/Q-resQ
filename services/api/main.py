"""FastAPI entrypoint. See BUILD_SPEC.md."""

from __future__ import annotations

from fastapi import FastAPI

from routers import requests as requests_router
from routers import benchmark, dispatch, log, risk, seed, units

app = FastAPI(title="PRAHARI API")
app.include_router(risk.router, prefix="/risk", tags=["risk"])
app.include_router(requests_router.router, prefix="/requests", tags=["requests"])
app.include_router(units.router, prefix="/units", tags=["units"])
app.include_router(dispatch.router, prefix="/dispatch", tags=["dispatch"])
app.include_router(benchmark.router, prefix="/benchmark", tags=["benchmark"])
app.include_router(log.router, prefix="/log", tags=["log"])
app.include_router(seed.router, prefix="/seed", tags=["seed"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
