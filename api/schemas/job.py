"""Job-related pydantic schemas."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class JobStatus(str, Enum):
    queued = "queued"
    collecting = "collecting"
    filtering = "filtering"
    summarizing = "summarizing"
    done = "done"
    failed = "failed"


class JobCreate(BaseModel):
    url: HttpUrl


class JobCreateResponse(BaseModel):
    job_id: str
    cached: bool = False
    result: dict | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: float = Field(0.0, ge=0.0, le=1.0)
    error: dict | None = None
