"""Prose summary prompt for the fine-tuned sLLM (served by vLLM).

Mirrors data_construction/summarize_project/summarize_with_gemini.py so that
inference-time prompts match training-time prompts exactly.
"""

from __future__ import annotations

from typing import Any


def build_transcript_text(transcript: list[dict[str, Any]]) -> str:
    """Join transcript segments into a single string."""
    return " ".join(
        item.get("text", "").strip()
        for item in transcript
        if item.get("text", "").strip()
    )


def build_comments_text(comments: list[dict[str, Any]]) -> str:
    """Format comment list as a numbered text block."""
    if not comments:
        return "(없음)"
    lines = [
        f"{i}. {c.get('text', '').strip()}"
        for i, c in enumerate(comments, 1)
        if c.get("text", "").strip()
    ]
    return "\n".join(lines) if lines else "(없음)"


def filter_passing_comments(
    comments: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
    prefix: str,
) -> list[dict[str, Any]]:
    """Return only comments whose evaluation entry has is_pass=True."""
    passing_indices = {
        int(e["id"][len(prefix):])
        for e in evaluations
        if e.get("is_pass") and e.get("id", "").startswith(prefix)
    }
    return [c for i, c in enumerate(comments) if i in passing_indices]


def build_summary_prompt(
    transcript_text: str,
    general_text: str,
    timestamp_text: str,
) -> str:
    """Compose the 3-paragraph prose summary prompt."""
    return f"""
당신은 유튜브 영상을 보고 독자에게 생생하게 전달하는 콘텐츠 작가입니다.
아래 세 가지 입력을 모두 소화하여 하나의 자연스러운 산문 요약을 작성해주세요.

[각 입력의 활용 방법]
- 자막: 영상의 전체 흐름과 내용 파악에만 사용
- 일반 댓글: 시청자들의 전반적인 반응과 여론 파악에만 사용
- 타임스탬프 댓글: 시청자들이 특히 집중하거나 반응한 장면과 시간 파악에만 사용

[산문 작성 규칙]
- 섹션 제목, 번호, 불릿 포인트 없이 문단으로만 구성
- 500~1000자 내외
- 아래 문단 흐름을 반드시 준수할 것:
  1문단 - 영상 내용: 자막만을 근거로 영상이 어떤 내용을 다루는지 서술.
           시간 정보(예: 3:24) 포함 금지.
  2문단 - 시청자 반응: 일반 댓글만을 근거로 시청자들의 전반적인 반응과 여론을 서술.
           시간 정보(예: 3:24) 포함 금지.
  3문단 - 집중 장면: 타임스탬프 댓글만을 근거로 시청자들이 특히 집중한 시간대와 그 반응을 서술.
           댓글에 기록된 시간 정보(예: 3:24)를 산문에 자연스럽게 녹여 쓸 것.
           예) "3:24에서는", "7:10 부근에서는"
- 각 문단은 자연스럽게 이어지도록 연결 표현을 사용할 것
- 문체는 '-이에요', '-요' 체로 통일하되 친근하고 자연스럽게

[절대 금지]
- 자막·댓글 문장을 단순히 나열하는 것
- 자막·댓글에 없는 내용을 추가하거나 사실을 지어내는 것
- 타임스탬프 댓글에 없는 시간 정보를 임의로 생성하는 것
- 각 문단의 소스를 혼용하는 것 (예: 1문단에 댓글 내용을 섞는 것)
- 1문단과 2문단에 시간 정보를 포함하는 것
- 근거 없는 추측이나 과장
- "이 영상은 매우 흥미로워요" 같은 평가성 도입 문장

[입력 데이터]
- 자막:
{transcript_text}

- 일반 댓글:
{general_text}

- 타임스탬프 댓글:
{timestamp_text}

산문만 출력하세요. 다른 텍스트는 포함하지 마세요.
"""
