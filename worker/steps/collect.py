"""Step 1: collect transcript + comments for a single YouTube video.

Thin async wrapper around :func:`worker.collectors.youtube_collector.collect_video_data`.
"""

from __future__ import annotations

import asyncio
from typing import Any

from shared.logging import get_logger
from worker.collectors import collect_video_data

logger = get_logger(__name__)


async def collect(
    video_url: str,
    max_regular: int,
    max_timestamp: int,
) -> dict[str, Any]:
    """Run the (blocking) collector in a thread and return its record.

    Args:
        video_url: Full YouTube URL submitted by the user.
        max_regular: Cap on the number of regular comments to collect.
        max_timestamp: Cap on the number of timestamp comments to collect.

    Returns:
        The record produced by ``collect_video_data`` (see its docstring
        for the exact shape).

    Raises:
        ValueError: When ``collect_video_data`` reports a failure (e.g.
            invalid video ID, subtitles disabled, geo-blocked). The message
            is formatted as ``"collect_failed:{reason}"``.
    """
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
