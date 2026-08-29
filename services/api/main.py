"""FastAPI entrypoint. See BUILD_SPEC.md."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import requests as requests_router
from routers import benchmark, dispatch, log, risk, seed, units

app = FastAPI(title="Q-resQ API")

# Frontend and backend deploy to separate domains (Vercel/Railway ->
# Railway), so the browser enforces CORS. ALLOWED_ORIGINS is a comma-
# separated env var set per-deploy; localhost is always allowed so the
# Vite dev server keeps working without any env var set.
_allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_allowed_origins += [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
