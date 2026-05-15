"""Thin async wrapper around the vLLM OpenAI-compatible endpoint."""

from __future__ import annotations

from openai import AsyncOpenAI


def make_vllm_client(base_url: str, api_key: str) -> AsyncOpenAI:
    return AsyncOpenAI(base_url=base_url, api_key=api_key)


async def generate_summary(
    client: AsyncOpenAI,
    model_name: str,
    prompt: str,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    top_p: float = 0.95,
) -> str:
    """Single-shot completion. Returns the generated text."""
    completion = await client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
    )
    return completion.choices[0].message.content or ""
