"""Job submission, status, and result endpoints."""

from __future__ import annotations

import uuid

from arq.connections import ArqRedis, create_pool, RedisSettings
from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_job_manager
from api.schemas import JobCreate, JobCreateResponse, JobStatusResponse
from api.services import JobManager
from api.settings import Settings, get_settings
from shared.youtube import extract_video_id

router = APIRouter(prefix="/jobs", tags=["jobs"])


_arq_pool: ArqRedis | None = None


async def _get_arq(settings: Settings) -> ArqRedis:
    """Lazily build the arq Redis pool from REDIS_URL."""
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    return _arq_pool


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    payload: JobCreate,
    settings: Settings = Depends(get_settings),
    jm: JobManager = Depends(get_job_manager),
) -> JobCreateResponse:
    video_id = extract_video_id(str(payload.url))
    if not video_id:
        raise HTTPException(status_code=400, detail="Could not parse YouTube video ID from URL.")

    cached = await jm.lookup_cache(video_id)
    if cached:
        cached_job_id, cached_payload = cached
        return JobCreateResponse(job_id=cached_job_id, cached=True, result=cached_payload)

    job_id = uuid.uuid4().hex
    await jm.create(job_id)

    arq = await _get_arq(settings)
    await arq.enqueue_job("run_pipeline", job_id=job_id, video_url=str(payload.url))

    return JobCreateResponse(job_id=job_id, cached=False)


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_status(
    job_id: str,
    jm: JobManager = Depends(get_job_manager),
) -> JobStatusResponse:
    meta = await jm.get_status(job_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobStatusResponse(
        job_id=job_id,
        status=meta["status"],
        progress=meta.get("progress", 0.0),
        error=meta.get("error"),
    )


@router.get("/{job_id}/result")
async def get_result(
    job_id: str,
    jm: JobManager = Depends(get_job_manager),
) -> dict:
    result = await jm.get_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found or not ready.")
    return result
