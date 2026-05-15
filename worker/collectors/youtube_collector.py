"""YouTube transcript and comment collector.

Collects transcript and comments (separated into timestamp comments and
regular comments) from a single YouTube video. This module is fully
self-contained — it only depends on third-party packages already listed in
`requirements.txt` (yt-dlp, youtube-transcript-api, youtube-comment-downloader).

Originally vendored from `data_construction/crawl_raw_data/youtube_collector.py`
and inlined into the web service so the worker does not need any `sys.path`
manipulation.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any


# ---------- timestamp parsing ----------

_STANDARD_PATTERN = r"(\d{1,2}):(\d{2})(?::(\d{2}))?"
_KOREAN_PATTERN = r"(\d+)분\s*(?:(\d+)초)?|(\d+)초"
_BRACKETED_PATTERN = r"[\[\(](\d{1,2}):(\d{2})(?::(\d{2}))?[\]\)]"


def parse_timestamp(text: str) -> list[tuple] | None:
    """Parse timestamp patterns out of a comment.

    Supports:
      - Standard ``M:SS`` / ``H:MM:SS`` (with word boundaries)
      - Bracketed ``[M:SS]`` / ``(M:SS)``
      - Korean ``1분 23초``, ``2분``, ``45초``

    Args:
        text: Raw comment text.

    Returns:
        List of regex match tuples if any timestamp was found, otherwise
        ``None``.
    """
    matches: list[tuple] = []

    m = re.findall(r"\b" + _STANDARD_PATTERN + r"\b", text)
    if m:
        matches.extend(m)

    m = re.findall(_BRACKETED_PATTERN, text)
    if m:
        matches.extend(m)

    m = re.findall(_KOREAN_PATTERN, text)
    if m:
        matches.extend(m)

    return matches if matches else None


# ---------- video metadata ----------

def get_video_length(video_url: str) -> int:
    """Return the video duration in seconds, or 0 if it cannot be determined.

    Uses yt-dlp's ``extract_info`` in metadata-only mode.

    Args:
        video_url: Full YouTube URL.

    Returns:
        Duration in seconds (int). 0 on failure.
    """
    try:
        import yt_dlp

        ydl_opts = {"quiet": True, "skip_download": True, "nocheckcertificate": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info.get("duration", 0)
    except Exception as e:  # noqa: BLE001
        print(f"Error getting video length: {e}")
        return 0


# ---------- transcript ----------

def _build_transcript_api():
    """Build a ``YouTubeTranscriptApi`` instance, honoring proxy env vars.

    Recognized environment variables:
        - ``WEBSHARE_PROXY_USERNAME`` / ``WEBSHARE_PROXY_PASSWORD``:
          rotating residential Webshare proxy.
        - ``TRANSCRIPT_HTTP_PROXY`` / ``TRANSCRIPT_HTTPS_PROXY``: generic
          HTTP/HTTPS proxy URL.

    Returns:
        A configured ``YouTubeTranscriptApi`` instance.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    webshare_user = os.environ.get("WEBSHARE_PROXY_USERNAME")
    webshare_pass = os.environ.get("WEBSHARE_PROXY_PASSWORD")
    http_proxy = os.environ.get("TRANSCRIPT_HTTP_PROXY")
    https_proxy = os.environ.get("TRANSCRIPT_HTTPS_PROXY")

    if webshare_user and webshare_pass:
        from youtube_transcript_api.proxies import WebshareProxyConfig

        print("  [Proxy] Using Webshare rotating residential proxy")
        return YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username=webshare_user,
                proxy_password=webshare_pass,
            )
        )
    if http_proxy or https_proxy:
        from youtube_transcript_api.proxies import GenericProxyConfig

        print(f"  [Proxy] Using generic proxy: {http_proxy or https_proxy}")
        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(
                http_url=http_proxy or https_proxy,
                https_url=https_proxy or http_proxy,
            )
        )
    return YouTubeTranscriptApi()


def _to_json_serializable(item: Any) -> dict[str, Any] | str:
    """Best-effort conversion of a transcript snippet to a plain dict.

    Args:
        item: Either a dict, a namedtuple-like (``_asdict``), an object with
            ``__dict__``, or a fallback object exposing ``text``/``start``/
            ``duration``.

    Returns:
        A dict if conversion succeeds, otherwise a string repr.
    """
    if isinstance(item, dict):
        return item
    if hasattr(item, "_asdict"):
        return item._asdict()
    if hasattr(item, "__dict__"):
        return vars(item)
    try:
        return {
            "text": getattr(item, "text", str(item)),
            "start": getattr(item, "start", 0),
            "duration": getattr(item, "duration", 0),
        }
    except Exception:  # noqa: BLE001
        return str(item)


def get_transcript(video_id: str, max_retries: int = 3):
    """Fetch a transcript for a YouTube video.

    Tries the manual ``ko``/``en`` transcript first, then falls back to the
    auto-generated one. Retries on HTTP 429 rate limits with exponential-ish
    backoff (30s, 60s, 90s).

    Args:
        video_id: 11-character YouTube video ID.
        max_retries: Maximum number of attempts on rate-limit errors.

    Returns:
        - ``list[dict]`` with transcript snippets on success
        - ``"subtitles_disabled"`` if the channel disabled subtitles
        - ``"geo_blocked"`` if the video is not available in this region
        - ``None`` on any other failure
    """

    def _fetch(api, vid: str):
        try:
            transcript_list = api.list(vid)
            transcript = transcript_list.find_transcript(["ko", "en"])
            result = transcript.fetch()
            return [_to_json_serializable(item) for item in result]
        except Exception:  # noqa: BLE001
            transcript_list = api.list(vid)
            transcript = transcript_list.find_generated_transcript(["ko", "en"])
            result = transcript.fetch()
            return [_to_json_serializable(item) for item in result]

    for attempt in range(1, max_retries + 1):
        try:
            api = _build_transcript_api()
            return _fetch(api, video_id)
        except Exception as e:  # noqa: BLE001
            err_str = str(e)
            if "Subtitles are disabled" in err_str:
                print(f"  [SKIP] Subtitles are disabled for video {video_id}")
                return "subtitles_disabled"
            is_geo_blocked = (
                "not made this video available in your country" in err_str
                or ("unplayable" in err_str.lower() and "country" in err_str.lower())
            )
            if is_geo_blocked:
                print(f"  [SKIP] Video not available in your country: {video_id}")
                return "geo_blocked"
            is_rate_limit = "429" in err_str or "too many" in err_str.lower()
            if is_rate_limit and attempt < max_retries:
                wait = 30 * attempt
                print(
                    f"  [429] Rate limited. Waiting {wait}s before retry "
                    f"{attempt}/{max_retries - 1}..."
                )
                time.sleep(wait)
            else:
                print(f"Error getting transcript: {e}")
                return None


# ---------- comments ----------

def is_meaningful_comment(text: str) -> bool:
    """Heuristic check that filters out spam/short/non-textual comments.

    A comment is considered meaningful when, after removing whitespace, it
    is at least 10 characters long, contains at least 10 Korean/alphanumeric
    characters, and those characters make up at least 40% of the comment.

    Args:
        text: Raw comment text.

    Returns:
        ``True`` if the comment passes the heuristic, ``False`` otherwise.
    """
    if not text:
        return False

    text_clean = re.sub(r"\s+", "", text)
    if len(text_clean) < 10:
        return False

    meaningful_chars = len(re.findall(r"[가-힣a-zA-Z0-9]", text))
    if meaningful_chars < 10:
        return False

    if meaningful_chars / len(text_clean) < 0.4:
        return False

    return True


def get_comments(
    video_url: str,
    sort_by: int = 0,
    max_regular: int = 50,
    max_timestamp: int = 50,
) -> tuple[list[dict[str, Any]] | str, list[dict[str, Any]] | None, int]:
    """Download comments from a YouTube video and split them by type.

    Comments are partitioned into timestamp comments (those containing a
    parseable timestamp) and regular comments. Reply comments (대댓글) are
    skipped. Up to ``max_scans_limit`` (50_000) comments are inspected.

    Args:
        video_url: Full YouTube URL.
        sort_by: 0 for Popular, 1 for Recent.
        max_regular: Cap on regular comments to collect.
        max_timestamp: Cap on timestamp comments to collect.

    Returns:
        Tuple of ``(timestamp_comments, regular_comments, scanned_count)``.
        On geo-block returns ``("geo_blocked", None, 0)``. On other errors
        returns ``(None, None, 0)``.
    """
    try:
        from youtube_comment_downloader import YoutubeCommentDownloader

        downloader = YoutubeCommentDownloader()
        generator = downloader.get_comments_from_url(video_url, sort_by=sort_by)

        timestamp_comments: list[dict[str, Any]] = []
        regular_comments: list[dict[str, Any]] = []

        max_scans_limit = 50000
        scanned_count = 0
        skipped_not_meaningful = 0

        for comment in generator:
            if comment.get("reply"):
                continue

            scanned_count += 1
            if scanned_count > max_scans_limit:
                break

            comment_text = comment.get("text", "")
            timestamps = parse_timestamp(comment_text)

            if timestamps:
                if len(timestamp_comments) < max_timestamp and comment_text.strip():
                    timestamp_comments.append({**comment, "timestamps_found": timestamps})
            elif is_meaningful_comment(comment_text):
                if len(regular_comments) < max_regular:
                    regular_comments.append(comment)
            else:
                skipped_not_meaningful += 1

            if (
                len(timestamp_comments) >= max_timestamp
                and len(regular_comments) >= max_regular
            ):
                break

        if scanned_count > 0:
            print(f"  - Scanned: {scanned_count} comments")
            print(f"  - Timestamp comments: {len(timestamp_comments)}")
            print(f"  - Regular comments: {len(regular_comments)}")
            if skipped_not_meaningful > 0:
                print(f"  - Skipped (not meaningful): {skipped_not_meaningful}")

        return timestamp_comments, regular_comments, scanned_count
    except Exception as e:  # noqa: BLE001
        err_str = str(e)
        if (
            "not made this video available in your country" in err_str
            or ("unplayable" in err_str.lower() and "country" in err_str.lower())
        ):
            print("  [SKIP] Video not available in your country")
            return "geo_blocked", None, 0
        print(f"Error getting comments: {e}")
        return None, None, 0


# ---------- url parsing ----------

_VIDEO_ID_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"),
    re.compile(r"youtube\.com/embed/([a-zA-Z0-9_-]{11})"),
]


def extract_video_id(url: str) -> str | None:
    """Return the 11-character YouTube video ID from a URL, or ``None``.

    Args:
        url: YouTube watch/short/embed URL.

    Returns:
        Video ID string if parseable, otherwise ``None``.
    """
    for pattern in _VIDEO_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


# ---------- top-level entrypoint ----------

def collect_video_data(
    video_url: str,
    max_regular: int = 50,
    max_timestamp: int = 50,
    sort_by: int = 0,
) -> dict[str, Any]:
    """Collect transcript + comments for a single YouTube video.

    This is the single function consumed by the worker's collect step. It
    composes ``get_video_length``, ``get_transcript`` and ``get_comments``
    into one record and reports a clear ``success``/``error`` status.

    Args:
        video_url: Full YouTube URL.
        max_regular: Max number of regular comments to collect.
        max_timestamp: Max number of timestamp comments to collect.
        sort_by: 0 for Popular, 1 for Recent.

    Returns:
        A dict with the following keys:
            ``video_url``, ``video_id``, ``success`` (bool), ``error``
            (only present on failure), ``video_length`` (seconds),
            ``transcript`` (list of snippet dicts), ``timestamp_comments``
            (list), ``regular_comments`` (list).
    """
    video_id = extract_video_id(video_url)
    if not video_id:
        print(f"Error: Could not extract video ID from {video_url}")
        return {
            "video_url": video_url,
            "success": False,
            "error": "Invalid video ID",
        }

    print(f"Processing video ID: {video_id}...")

    duration = get_video_length(video_url)
    transcript = get_transcript(video_id)

    if transcript in ("subtitles_disabled", "geo_blocked"):
        return {
            "video_url": video_url,
            "video_id": video_id,
            "success": False,
            "error": transcript,
            "video_length": duration,
            "transcript": [],
            "timestamp_comments": [],
            "regular_comments": [],
        }

    timestamp_comments, regular_comments, _ = get_comments(
        video_url,
        sort_by=sort_by,
        max_regular=max_regular,
        max_timestamp=max_timestamp,
    )

    if timestamp_comments == "geo_blocked":
        return {
            "video_url": video_url,
            "video_id": video_id,
            "success": False,
            "error": "geo_blocked",
            "video_length": duration,
            "transcript": transcript if transcript else [],
            "timestamp_comments": [],
            "regular_comments": [],
        }

    success = (
        transcript is not None
        and timestamp_comments is not None
        and regular_comments is not None
    )

    return {
        "video_url": video_url,
        "video_id": video_id,
        "success": success,
        "video_length": duration,
        "transcript": transcript if transcript else [],
        "timestamp_comments": timestamp_comments if timestamp_comments else [],
        "regular_comments": regular_comments if regular_comments else [],
    }
