"""Summary result schemas."""

from __future__ import annotations

from pydantic import BaseModel


class SummaryParagraphs(BaseModel):
    content: str       # 1문단 — 영상 내용
    reaction: str      # 2문단 — 시청자 반응
    highlights: str    # 3문단 — 집중 장면


class FilterStats(BaseModel):
    total_general: int
    total_timestamp: int
    passed_general: int
    passed_timestamp: int


class SummaryResult(BaseModel):
    video_id: str
    video_url: str
    title: str | None = None
    channel_name: str | None = None
    summary: SummaryParagraphs | None = None
    raw_summary: str
    filter_stats: FilterStats
