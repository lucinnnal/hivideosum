"""Smoke tests for prompt helpers (no network, no LLM calls)."""

from inference.prompts import (
    build_filter_prompt,
    build_summary_prompt,
    filter_passing_comments,
    parse_evaluation_response,
)


def test_filter_prompt_contains_inputs():
    prompt = build_filter_prompt(
        transcript_text="안녕하세요",
        regular_comments=[{"text": "재미있어요"}],
        timestamp_comments=[{"text": "3:24 부분 좋아요"}],
    )
    assert "안녕하세요" in prompt
    assert "재미있어요" in prompt
    assert "3:24" in prompt


def test_parse_evaluation_response_basic():
    text = "g0|1|2|1|4|Fail\ng1|3|3|3|9|Pass\nt0|2|2|2|6|Pass\n"
    result = parse_evaluation_response(text)
    assert len(result["general_comments"]) == 2
    assert len(result["timestamp_comments"]) == 1
    assert result["general_comments"][1]["is_pass"] is True
    assert result["timestamp_comments"][0]["total_score"] == 6


def test_filter_passing_comments_keeps_passed_only():
    comments = [{"text": "a"}, {"text": "b"}, {"text": "c"}]
    evaluations = [
        {"id": "g0", "is_pass": True},
        {"id": "g1", "is_pass": False},
        {"id": "g2", "is_pass": True},
    ]
    passed = filter_passing_comments(comments, evaluations, "g")
    assert [c["text"] for c in passed] == ["a", "c"]


def test_summary_prompt_has_three_paragraph_rule():
    prompt = build_summary_prompt("자막", "댓글1\n댓글2", "타임스탬프 댓글")
    assert "1문단" in prompt
    assert "2문단" in prompt
    assert "3문단" in prompt
