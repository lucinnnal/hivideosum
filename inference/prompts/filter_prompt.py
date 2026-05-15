"""3-axis comment filtering prompt for Vertex AI Gemini.

Reuses the prompt and parsing logic from
data_construction/crawl_raw_data/filter_comments_with_gemini.py.
"""

from __future__ import annotations

import json
from typing import Any


PROMPT_TEMPLATE = """
당신은 YouTube 영상의 댓글을 분석하고 필터링하는 전문가입니다.
당신의 목표는 주어진 Transcript(영상 자막/대본)를 바탕으로, 시청자들의 유의미한 반응과 정보가 담긴 댓글을 선별하는 것입니다. 아래의 평가 기준에 따라 각 댓글에 점수를 매기고, 총점이 6점 이상인 댓글만 '통과(Pass)'로 분류하세요.

[평가 기준]
1. 정보성 (1-3점): 댓글이 의미 있는 정보나 요약을 담고 있는가?
- 1점: 내용이 없거나 무의미한 텍스트 (예: "ㅋㅋ", "1빠", 스팸)
- 2점: 영상에 등장하는 단편적인 사실을 언급함
- 3점: 영상 내용을 훌륭하게 요약했거나, 영상과 관련된 유용한 추가 정보/인사이트를 제공함

2. 의견성 (1-3점): 시청자의 주관적인 의견, 감정, 반응이 잘 담겨 있는가?
- 1점: 의견이나 감정이 전혀 드러나지 않음 (단순 사실 나열)
- 2점: 평범하고 일상적인 반응 (예: "잘 봤습니다", "재밌네요")
- 3점: 영상에 대한 깊은 공감, 날카로운 비판, 또는 독창적인 시각이나 강렬한 주관적 감정이 드러남

3. 연관성 (1-3점): 제공된 Transcript의 내용과 직접적으로 연관되어 있는가?
- 1점: 영상의 내용과 전혀 무관함 (딴소리, 어그로)
- 2점: 영상의 전반적인 주제와는 관련이 있으나, 구체적인 내용은 아님
- 3점: Transcript에 등장하는 특정 발언, 장면, 맥락을 정확히 짚어서 이야기함

[평가 규칙]
- 총점 = 정보성 + 의견성 + 연관성
- 총점이 6점 이상(>= 6)인 경우에만 "Pass"로 분류하세요. 미만인 경우 "Fail"로 분류합니다.
- 아래의 [출력 형식]과 같이 각 줄마다 `댓글ID|정보성점수|의견성점수|연관성점수|총점|Pass/Fail` 형식으로만 출력하십시오.
- 헤더, 인사말, 마크다운(예: ```) 등 다른 텍스트는 절대 포함하지 마십시오. 오로지 각 댓글에 대한 결과만 한 줄씩 출력해야 합니다.

[출력 형식 예시]
g0|1|2|1|4|Fail
g1|2|3|3|8|Pass
t0|1|1|1|3|Fail
t1|3|3|2|8|Pass

[입력 데이터]
## Transcript
\"\"\"
{transcript}
\"\"\"

## 일반 댓글
{general_comments}

## Timestamp 댓글
{timestamp_comments}
"""


def prepare_comments_for_prompt(
    comments: list[dict[str, Any]],
    id_prefix: str,
) -> str:
    """Format comments as JSON with stable IDs (g0, g1, t0, ...)."""
    formatted = [
        {"id": f"{id_prefix}{idx}", "text": c.get("text", "").strip()}
        for idx, c in enumerate(comments)
    ]
    return json.dumps(formatted, ensure_ascii=False, indent=2)


def build_filter_prompt(
    transcript_text: str,
    regular_comments: list[dict[str, Any]],
    timestamp_comments: list[dict[str, Any]],
) -> str:
    """Compose the final filter prompt for one video."""
    return PROMPT_TEMPLATE.format(
        transcript=transcript_text,
        general_comments=prepare_comments_for_prompt(regular_comments, "g"),
        timestamp_comments=prepare_comments_for_prompt(timestamp_comments, "t"),
    )


def parse_evaluation_response(response_text: str) -> dict[str, list[dict[str, Any]]]:
    """Parse the pipe-separated Gemini response into structured evaluation results.

    Returns:
        {
          "general_comments":   [{"id","scores","total_score","is_pass"}, ...],
          "timestamp_comments": [...],
        }
    """
    text = response_text.strip()
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    general: list[dict[str, Any]] = []
    timestamp: list[dict[str, Any]] = []

    for line in text.split("\n"):
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 6:
            continue
        try:
            c_id = parts[0]
            info = int(parts[1])
            opinion = int(parts[2])
            relevance = int(parts[3])
            total = int(parts[4])
            is_pass = parts[5].lower() == "pass"
        except ValueError:
            continue

        entry = {
            "id": c_id,
            "scores": {"info": info, "opinion": opinion, "relevance": relevance},
            "total_score": total,
            "is_pass": is_pass,
        }
        if c_id.startswith("g"):
            general.append(entry)
        elif c_id.startswith("t"):
            timestamp.append(entry)

    return {"general_comments": general, "timestamp_comments": timestamp}
