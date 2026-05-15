"""Step 3: call the fine-tuned sLLM via vLLM to produce the 3-paragraph summary."""

from __future__ import annotations

import re
from typing import Any

from openai import AsyncOpenAI

from api.services import generate_summary
from inference.prompts import (
    build_comments_text,
    build_summary_prompt,
    build_transcript_text,
    filter_passing_comments,
)
from shared.logging import get_logger

logger = get_logger(__name__)


def _split_paragraphs(text: str) -> tuple[str, str, str]:
    """Split prose into (content, reaction, highlights) by blank lines.

    The training prompt requires exactly 3 paragraphs. If the model returns
    fewer or more, we keep the first three (padding with empty strings).
    """
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text.strip()) if p.strip()]
    paragraphs = (paragraphs + ["", "", ""])[:3]
    return paragraphs[0], paragraphs[1], paragraphs[2]


async def summarize(
    record: dict[str, Any],
    vllm_client: AsyncOpenAI,
    model_name: str,
) -> dict[str, Any]:
    """Compose the prompt and call vLLM. Returns a result dict ready to persist."""
    transcript_text = build_transcript_text(record.get("transcript", []))

    evaluation = record.get("evaluation_result", {}) or {}
    raw_general = record.get("regular_comments", []) or []
    raw_timestamp = record.get("timestamp_comments", []) or []
    passed_general = filter_passing_comments(raw_general, evaluation.get("general_comments", []), "g")
    passed_timestamp = filter_passing_comments(raw_timestamp, evaluation.get("timestamp_comments", []), "t")

    general_text = build_comments_text(passed_general)
    timestamp_text = build_comments_text(passed_timestamp)

    prompt = build_summary_prompt(transcript_text, general_text, timestamp_text)
    logger.info("Calling vLLM model=%s prompt_chars=%d", model_name, len(prompt))

    raw_summary = await generate_summary(vllm_client, model_name, prompt)
    p1, p2, p3 = _split_paragraphs(raw_summary)

    return {
        "video_id": record.get("video_id"),
        "video_url": record.get("video_url"),
        "title": record.get("title"),
        "channel_name": record.get("channel_name"),
        "summary": {"content": p1, "reaction": p2, "highlights": p3},
        "raw_summary": raw_summary,
        "filter_stats": {
            "total_general": len(raw_general),
            "total_timestamp": len(raw_timestamp),
            "passed_general": len(passed_general),
            "passed_timestamp": len(passed_timestamp),
        },
    }
