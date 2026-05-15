"""Step 2: filter comments via Vertex AI Gemini 3 Flash Preview.

Reuses the 3-axis evaluation prompt and parser from inference/prompts/.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import yaml
from google import genai
from google.genai import types

from inference.prompts import (
    build_filter_prompt,
    build_transcript_text,
    parse_evaluation_response,
)
from shared.logging import get_logger

logger = get_logger(__name__)


# ---------- client / config ----------

def make_gemini_client(project: str, location: str) -> genai.Client:
    """Vertex AI client. Uses ADC or GOOGLE_APPLICATION_CREDENTIALS."""
    return genai.Client(vertexai=True, project=project, location=location)


def load_filter_config(path: str) -> tuple[str, types.GenerateContentConfig]:
    """Load filter_gemini.yaml → (model_name, GenerateContentConfig)."""
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    model_name = cfg.get("model_name", "gemini-3-flash-preview")
    gen = cfg.get("generation", {}) or {}
    thinking_level = (gen.get("thinking") or {}).get("thinking_level")

    return model_name, types.GenerateContentConfig(
        temperature=gen.get("temperature", 0.1),
        top_p=gen.get("top_p", 0.95),
        max_output_tokens=gen.get("max_output_tokens", 4096),
        thinking_config=(
            types.ThinkingConfig(thinking_level=thinking_level) if thinking_level else None
        ),
    )


# ---------- filter step ----------

async def filter_comments(
    record: dict[str, Any],
    client: genai.Client,
    model_name: str,
    gen_config: types.GenerateContentConfig,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Run Gemini 3-axis filter on one record.

    Mutates `record` in place by attaching `evaluation_result`, and returns it.
    """
    transcript_text = build_transcript_text(record.get("transcript", []))
    regular = record.get("regular_comments", []) or []
    timestamp = record.get("timestamp_comments", []) or []

    if not regular and not timestamp:
        record["evaluation_result"] = {"general_comments": [], "timestamp_comments": []}
        return record

    prompt = build_filter_prompt(transcript_text, regular, timestamp)

    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=prompt,
                config=gen_config,
            )
            evaluation = parse_evaluation_response(response.text or "")
            record["evaluation_result"] = evaluation
            return record
        except Exception as e:  # noqa: BLE001
            last_err = e
            msg = str(e)
            transient = "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg
            if attempt < max_retries and transient:
                wait = 5 * attempt
                logger.warning("Gemini filter rate-limited; retry %d/%d in %ds", attempt, max_retries, wait)
                await asyncio.sleep(wait)
                continue
            break

    raise RuntimeError(f"filter_failed: {last_err}")
