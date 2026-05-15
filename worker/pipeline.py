"""End-to-end pipeline: collect → filter → summarize, with progress updates."""

from __future__ import annotations

from typing import Any

from api.schemas import JobStatus
from api.services import JobManager
from api.settings import Settings
from shared.logging import get_logger
from worker.steps import collect, filter_comments, summarize

logger = get_logger(__name__)


async def run_pipeline(
    job_id: str,
    video_url: str,
    *,
    jm: JobManager,
    settings: Settings,
    gemini_client,
    gemini_model: str,
    gemini_gen_config,
    vllm_client,
) -> dict[str, Any]:
    """Execute the three steps sequentially. Persists result via JobManager."""
    # Step 1
    await jm.update_status(job_id, JobStatus.collecting, progress=0.1)
    record = await collect(video_url, settings.COLLECT_MAX_REGULAR, settings.COLLECT_MAX_TIMESTAMP)

    # Step 2
    await jm.update_status(job_id, JobStatus.filtering, progress=0.4)
    record = await filter_comments(record, gemini_client, gemini_model, gemini_gen_config)

    # Step 3
    await jm.update_status(job_id, JobStatus.summarizing, progress=0.75)
    payload = await summarize(record, vllm_client, settings.VLLM_MODEL_NAME)

    video_id = payload["video_id"]
    await jm.save_result(job_id, video_id, payload)
    logger.info("Pipeline done: job=%s video=%s", job_id, video_id)
    return payload
