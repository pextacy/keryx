"""LLM judge + answerer: structured mapping, resilient fallback, and factory wiring.

No network: a fake Anthropic client stands in for the SDK so the moat's mapping and
degrade-to-heuristic behavior are tested deterministically in CI.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from agent.answerer import AnthropicAnswerer, ExtractiveAnswerer
from agent.factory import build_answerer, build_judge, build_scorer
from agent.grounding.judge import (
    AnthropicJudge,
    HeuristicJudge,
    Verdict,
    _ClaimVerdict,
    _JudgeOutput,
)
from registry.models import Source
from shared.config import Settings

ANSWER = "Gateway batches USDC authorizations and settles them on Arc sub-cent."
SOURCE = "Circle Gateway batches small USDC authorizations and settles them on Arc."


class _FakeParse:
    def __init__(self, parsed: Any | None = None, raises: Exception | None = None) -> None:
        self._parsed = parsed
        self._raises = raises

    def parse(self, **_: Any) -> Any:
        if self._raises is not None:
            raise self._raises
        return SimpleNamespace(parsed_output=self._parsed)

    def create(self, **_: Any) -> Any:
        if self._raises is not None:
            raise self._raises
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._parsed)])


class _FakeClient:
    def __init__(self, parsed: Any | None = None, raises: Exception | None = None) -> None:
        self.messages = _FakeParse(parsed, raises)


def _src(sid: str, text: str) -> Source:
    return Source(source_id=sid, url=f"https://x/{sid}", title="T", text=text, author="a")


# --- AnthropicJudge ---------------------------------------------------------


def test_judge_maps_structured_verdicts() -> None:
    parsed = _JudgeOutput(
        claims=[
            _ClaimVerdict(claim="Gateway batches USDC", verdict=Verdict.SUPPORTED),
            _ClaimVerdict(claim="settles on Arc", verdict=Verdict.SUPPORTED),
        ],
        rationale="both claims directly stated by source",
    )
    judge = AnthropicJudge(_FakeClient(parsed=parsed), model="claude-opus-4-8")
    jr = judge.judge(ANSWER, SOURCE)
    assert jr.verdict is Verdict.SUPPORTED
    assert len(jr.per_claim) == 2
    assert jr.rationale.startswith("[claude:claude-opus-4-8]")


def test_judge_overall_is_partial_when_mixed() -> None:
    parsed = _JudgeOutput(
        claims=[
            _ClaimVerdict(claim="a", verdict=Verdict.SUPPORTED),
            _ClaimVerdict(claim="b", verdict=Verdict.UNSUPPORTED),
        ],
        rationale="mixed",
    )
    judge = AnthropicJudge(_FakeClient(parsed=parsed), model="m")
    assert judge.judge(ANSWER, SOURCE).verdict is Verdict.PARTIAL


def test_judge_falls_back_to_heuristic_on_error() -> None:
    judge = AnthropicJudge(_FakeClient(raises=RuntimeError("boom")), model="m")
    jr = judge.judge(ANSWER, SOURCE)
    assert jr.rationale.startswith("[fallback:heuristic]")
    # Heuristic still produces a usable verdict on an on-topic source.
    assert jr.verdict in (Verdict.SUPPORTED, Verdict.PARTIAL)


def test_judge_empty_inputs_unsupported() -> None:
    judge = AnthropicJudge(_FakeClient(parsed=None), model="m")
    assert judge.judge("", SOURCE).verdict is Verdict.UNSUPPORTED


def test_judge_no_claims_unsupported() -> None:
    parsed = _JudgeOutput(claims=[], rationale="nothing")
    judge = AnthropicJudge(_FakeClient(parsed=parsed), model="m")
    assert judge.judge(ANSWER, SOURCE).verdict is Verdict.UNSUPPORTED


# --- AnthropicAnswerer ------------------------------------------------------


def test_answerer_returns_model_text() -> None:
    ans = AnthropicAnswerer(_FakeClient(parsed="Gateway settles on Arc."), model="m")
    assert ans.answer("q", [_src("s1", "Gateway settles on Arc.")]) == "Gateway settles on Arc."


def test_answerer_falls_back_on_error() -> None:
    ans = AnthropicAnswerer(_FakeClient(raises=RuntimeError("boom")), model="m")
    out = ans.answer("Gateway", [_src("s1", "Gateway settles on Arc. It is sub-cent.")])
    assert out  # extractive fallback produced something
    assert "Arc" in out


def test_answerer_no_sources() -> None:
    ans = AnthropicAnswerer(_FakeClient(parsed="x"), model="m")
    assert "No sources" in ans.answer("q", [])


# --- Factory wiring ---------------------------------------------------------


def test_factory_uses_heuristics_without_key() -> None:
    cfg = Settings(anthropic_api_key="")
    assert isinstance(build_judge(cfg), HeuristicJudge)
    assert isinstance(build_answerer(cfg), ExtractiveAnswerer)
    assert isinstance(build_scorer(cfg).judge, HeuristicJudge)


def test_factory_uses_claude_with_key() -> None:
    cfg = Settings(anthropic_api_key="sk-ant-test")
    assert isinstance(build_judge(cfg), AnthropicJudge)
    assert isinstance(build_answerer(cfg), AnthropicAnswerer)
    assert isinstance(build_scorer(cfg).judge, AnthropicJudge)
