"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routers import health, jobs
from shared.logging import setup_logging

setup_logging()

app = FastAPI(title="Hi-VideoSum", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(jobs.router)

# Optional simple frontend at /ui
try:
    app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")
except RuntimeError:
    # frontend directory missing in test runs
    pass
