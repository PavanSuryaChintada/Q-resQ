"""FastAPI entrypoint. See BUILD_SPEC.md."""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="PRAHARI API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
