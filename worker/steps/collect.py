"""Step 1: collect transcript + comments for a single YouTube video.

Wraps data_construction/crawl_raw_data/youtube_collector.collect_video_data.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from api.settings import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)


def _ensure_crawl_module_on_path() -> None:
    """Add the existing crawl_raw_data directory to sys.path so we can import it."""
    settings = get_settings()
    crawl_path = os.path.abspath(settings.CRAWL_RAW_DATA_PATH)
    if crawl_path not in sys.path:
        sys.path.insert(0, crawl_path)


async def collect(
    video_url: str,
    max_regular: int,
    max_timestamp: int,
) -> dict[str, Any]:
    """Run the (blocking) collector in a thread.

    Returns the collected record produced by collect_video_data.
    Raises ValueError on unrecoverable errors (invalid id, subtitles disabled, geo-blocked).
    """
    _ensure_crawl_module_on_path()
    from youtube_collector import collect_video_data  # noqa: E402

    logger.info("Collecting %s", video_url)
    record = await asyncio.to_thread(
        collect_video_data,
        video_url,
        max_regular,
        max_timestamp,
        0,  # sort_by=0 → popular
    )

    if not record.get("success"):
        err = record.get("error") or "collection_failed"
        raise ValueError(f"collect_failed:{err}")

    return record
