"""arq worker entrypoint.

Run with:  arq worker.runner.WorkerSettings
"""

from __future__ import annotations

from arq.connections import RedisSettings
from redis.asyncio import from_url

from api.services import JobManager, make_vllm_client
from api.settings import get_settings
from shared.logging import setup_logging
from worker.pipeline import run_pipeline as _run_pipeline_impl
from worker.steps import load_filter_config, make_gemini_client


async def startup(ctx: dict) -> None:
    setup_logging()
    settings = get_settings()
    ctx["settings"] = settings

    ctx["redis_async"] = from_url(settings.REDIS_URL, decode_responses=False)
    ctx["jm"] = JobManager(redis=ctx["redis_async"], result_ttl=settings.RESULT_TTL_SECONDS)

    ctx["gemini_client"] = make_gemini_client(settings.GCP_PROJECT, settings.GCP_LOCATION)
    ctx["gemini_model"], ctx["gemini_gen_config"] = load_filter_config(settings.FILTER_CONFIG_PATH)

    ctx["vllm_client"] = make_vllm_client(settings.VLLM_BASE_URL, settings.VLLM_API_KEY)


async def shutdown(ctx: dict) -> None:
    redis = ctx.get("redis_async")
    if redis is not None:
        await redis.close()


async def run_pipeline(ctx: dict, *, job_id: str, video_url: str) -> dict:
    from api.schemas import JobStatus

    jm: JobManager = ctx["jm"]
    try:
        return await _run_pipeline_impl(
            job_id=job_id,
            video_url=video_url,
            jm=jm,
            settings=ctx["settings"],
            gemini_client=ctx["gemini_client"],
            gemini_model=ctx["gemini_model"],
            gemini_gen_config=ctx["gemini_gen_config"],
            vllm_client=ctx["vllm_client"],
        )
    except Exception as e:  # noqa: BLE001
        code, _, msg = str(e).partition(":")
        await jm.set_error(job_id, code=code or "pipeline_error", message=msg or str(e))
        raise


class WorkerSettings:
    functions = [run_pipeline]
    on_startup = startup
    on_shutdown = shutdown
    job_timeout = 600  # 10 min
    max_jobs = 4
    redis_settings = RedisSettings.from_dsn(get_settings().REDIS_URL)
