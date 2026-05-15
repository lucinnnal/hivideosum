"""YouTube URL handling utilities."""

from __future__ import annotations

import re

_VIDEO_ID_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"),
    re.compile(r"youtube\.com/embed/([a-zA-Z0-9_-]{11})"),
    re.compile(r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})"),
]


def extract_video_id(url: str) -> str | None:
    """Return the 11-char YouTube video ID, or None if not parseable."""
    for pattern in _VIDEO_ID_PATTERNS:
        m = pattern.search(url)
        if m:
            return m.group(1)
    return None


def canonical_url(video_id: str) -> str:
    """Return the canonical watch URL for a video ID."""
    return f"https://www.youtube.com/watch?v={video_id}"
