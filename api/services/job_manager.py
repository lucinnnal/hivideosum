"""Redis-backed job state and cache.

Keys:
  job:{job_id}:meta         hash  status, progress, error
  job:{job_id}:result       string JSON SummaryResult
  cache:video:{video_id}    string job_id   (links a video to its latest result)
"""

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from api.schemas import JobStatus


class JobManager:
    def __init__(self, redis: Redis, result_ttl: int):
        self.redis = redis
        self.result_ttl = result_ttl

    # ---------- keys ----------
    @staticmethod
    def _meta_key(job_id: str) -> str:
        return f"job:{job_id}:meta"

    @staticmethod
    def _result_key(job_id: str) -> str:
        return f"job:{job_id}:result"

    @staticmethod
    def _cache_key(video_id: str) -> str:
        return f"cache:video:{video_id}"

    # ---------- state ----------
    async def create(self, job_id: str) -> None:
        await self.redis.hset(
            self._meta_key(job_id),
            mapping={"status": JobStatus.queued.value, "progress": "0.0"},
        )
        await self.redis.expire(self._meta_key(job_id), self.result_ttl)

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: float | None = None,
    ) -> None:
        mapping: dict[str, str] = {"status": status.value}
        if progress is not None:
            mapping["progress"] = str(progress)
        await self.redis.hset(self._meta_key(job_id), mapping=mapping)

    async def set_error(self, job_id: str, code: str, message: str) -> None:
        await self.redis.hset(
            self._meta_key(job_id),
            mapping={
                "status": JobStatus.failed.value,
                "error": json.dumps({"code": code, "message": message}, ensure_ascii=False),
            },
        )

    async def get_status(self, job_id: str) -> dict[str, Any] | None:
        raw = await self.redis.hgetall(self._meta_key(job_id))
        if not raw:
            return None
        out: dict[str, Any] = {k.decode(): v.decode() for k, v in raw.items()}
        out["progress"] = float(out.get("progress", 0.0))
        if "error" in out:
            out["error"] = json.loads(out["error"])
        return out

    # ---------- results ----------
    async def save_result(self, job_id: str, video_id: str, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False)
        await self.redis.set(self._result_key(job_id), body, ex=self.result_ttl)
        await self.redis.set(self._cache_key(video_id), job_id, ex=self.result_ttl)
        await self.update_status(job_id, JobStatus.done, progress=1.0)

    async def get_result(self, job_id: str) -> dict | None:
        body = await self.redis.get(self._result_key(job_id))
        return json.loads(body) if body else None

    async def lookup_cache(self, video_id: str) -> tuple[str, dict] | None:
        """If a result for this video_id is cached, return (job_id, payload)."""
        job_id_bytes = await self.redis.get(self._cache_key(video_id))
        if not job_id_bytes:
            return None
        job_id = job_id_bytes.decode()
        payload = await self.get_result(job_id)
        if payload is None:
            return None
        return job_id, payload
