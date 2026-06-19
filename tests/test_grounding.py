"""Grounding moat: similarity + judge -> g, gate at T, weighted amount."""

from __future__ import annotations

from decimal import Decimal

from agent.grounding import GroundingScorer, HeuristicJudge, Verdict, cosine, similarity

ON_TOPIC = (
    "Circle Gateway batches small USDC authorizations and settles them on Arc, "
    "removing the per-payment fee floor so a sub-cent citation toll can clear."
)
ANSWER = "Gateway batches USDC authorizations and settles them on Arc sub-cent."
OFF_TOPIC = "Tomatoes need full sun, regular watering, and well-drained soil."


def test_cosine_bounds_and_identity() -> None:
    assert similarity("hello world", "hello world") > 0.99
    assert cosine({}, {"a": 1.0}) == 0.0
    assert similarity("abc", "xyz") == 0.0


def test_similarity_prefers_on_topic() -> None:
    assert similarity(ANSWER, ON_TOPIC) > similarity(ANSWER, OFF_TOPIC)


def test_heuristic_judge_supported_vs_unsupported() -> None:
    j = HeuristicJudge()
    assert j.judge(ANSWER, ON_TOPIC).verdict in (Verdict.SUPPORTED, Verdict.PARTIAL)
    assert j.judge(ANSWER, OFF_TOPIC).verdict is Verdict.UNSUPPORTED


def test_scorer_gates_on_topic_above_offtopic() -> None:
    scorer = GroundingScorer()
    on = scorer.score(source_id="on", answer=ANSWER, source_text=ON_TOPIC)
    off = scorer.score(source_id="off", answer=ANSWER, source_text=OFF_TOPIC)
    assert on.g > off.g
    assert on.cited is True and on.amount > Decimal(0)
    assert off.cited is False and off.amount == Decimal(0)
    assert "g=" in on.rationale


def test_amount_scales_with_g_within_band() -> None:
    scorer = GroundingScorer()
    lo = scorer.amount_for(0.5)
    hi = scorer.amount_for(1.0)
    assert scorer.cfg.citation_toll_min <= lo <= hi <= scorer.cfg.citation_toll_max
