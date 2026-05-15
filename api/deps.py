"""FastAPI dependencies (Redis, job manager)."""

from __future__ import annotations

from functools import lru_cache
from typing import AsyncIterator

from fastapi import Depends
from redis.asyncio import Redis, from_url

from api.services import JobManager
from api.settings import Settings, get_settings


@lru_cache
def _redis_pool(redis_url: str) -> Redis:
    return from_url(redis_url, decode_responses=False)


async def get_redis(settings: Settings = Depends(get_settings)) -> AsyncIterator[Redis]:
    yield _redis_pool(settings.REDIS_URL)


async def get_job_manager(
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> JobManager:
    return JobManager(redis=redis, result_ttl=settings.RESULT_TTL_SECONDS)
