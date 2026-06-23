"""LLM judge + answerer: structured mapping, resilient fallback, and factory wiring.

No network: a fake Gemini client stands in for the SDK so the moat's mapping and
degrade-to-heuristic behavior are tested deterministically in CI.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from agent.answerer import ExtractiveAnswerer, GeminiAnswerer
from agent.factory import build_answerer, build_judge, build_scorer
from agent.grounding.judge import (
    GeminiJudge,
    HeuristicJudge,
    Verdict,
    _ClaimVerdict,
    _JudgeOutput,
)
from agent.llm import call_with_retry
from registry.models import Source
from shared.config import Settings

ANSWER = "Gateway batches USDC authorizations and settles them on Arc sub-cent."
SOURCE = "Circle Gateway batches small USDC authorizations and settles them on Arc."


class _TransientError(Exception):
    """Mimics a google.genai APIError: carries an HTTP status in ``.code`` (429/5xx)."""

    def __init__(self, code: int) -> None:
        super().__init__(f"transient {code}")
        self.code = code


class _FakeGeminiModels:
    def __init__(
        self,
        parsed: Any | None = None,
        raises: Exception | None = None,
        *,
        fail_times: int = 0,
    ) -> None:
        self._parsed = parsed
        self._raises = raises
        self._fail_times = fail_times
        self.calls = 0

    def generate_content(self, **_: Any) -> Any:
        self.calls += 1
        # Transient failures for the first ``fail_times`` calls, then succeed.
        if self._fail_times and self.calls <= self._fail_times:
            raise _TransientError(503)
        if self._raises is not None:
            raise self._raises
        # Gemini returns `.parsed` (structured) and `.text` (free-form).
        text = self._parsed if isinstance(self._parsed, str) else None
        return SimpleNamespace(parsed=self._parsed, text=text)


class _FakeGeminiClient:
    def __init__(
        self,
        parsed: Any | None = None,
        raises: Exception | None = None,
        *,
        fail_times: int = 0,
    ) -> None:
        self.models = _FakeGeminiModels(parsed, raises, fail_times=fail_times)


def _src(sid: str, text: str) -> Source:
    return Source(source_id=sid, url=f"https://x/{sid}", title="T", text=text, author="a")


# --- GeminiJudge ------------------------------------------------------------


def test_judge_maps_structured_verdicts() -> None:
    parsed = _JudgeOutput(
        claims=[
            _ClaimVerdict(claim="Gateway batches USDC", verdict=Verdict.SUPPORTED),
            _ClaimVerdict(claim="settles on Arc", verdict=Verdict.SUPPORTED),
        ],
        rationale="both claims directly stated by source",
    )
    judge = GeminiJudge(_FakeGeminiClient(parsed=parsed), model="gemini-2.5-flash")
    jr = judge.judge(ANSWER, SOURCE)
    assert jr.verdict is Verdict.SUPPORTED
    assert len(jr.per_claim) == 2
    assert jr.rationale.startswith("[gemini:gemini-2.5-flash]")


def test_judge_overall_is_partial_when_mixed() -> None:
    parsed = _JudgeOutput(
        claims=[
            _ClaimVerdict(claim="a", verdict=Verdict.SUPPORTED),
            _ClaimVerdict(claim="b", verdict=Verdict.UNSUPPORTED),
        ],
        rationale="mixed",
    )
    judge = GeminiJudge(_FakeGeminiClient(parsed=parsed), model="m")
    assert judge.judge(ANSWER, SOURCE).verdict is Verdict.PARTIAL


def test_judge_falls_back_to_heuristic_on_error() -> None:
    judge = GeminiJudge(_FakeGeminiClient(raises=RuntimeError("boom")), model="m")
    jr = judge.judge(ANSWER, SOURCE)
    assert jr.rationale.startswith("[fallback:heuristic]")
    # Heuristic still produces a usable verdict on an on-topic source.
    assert jr.verdict in (Verdict.SUPPORTED, Verdict.PARTIAL)


def test_judge_empty_inputs_unsupported() -> None:
    judge = GeminiJudge(_FakeGeminiClient(parsed=None), model="m")
    assert judge.judge("", SOURCE).verdict is Verdict.UNSUPPORTED


def test_judge_no_claims_unsupported() -> None:
    parsed = _JudgeOutput(claims=[], rationale="nothing")
    judge = GeminiJudge(_FakeGeminiClient(parsed=parsed), model="m")
    assert judge.judge(ANSWER, SOURCE).verdict is Verdict.UNSUPPORTED


# --- GeminiAnswerer ---------------------------------------------------------


def test_answerer_returns_model_text() -> None:
    ans = GeminiAnswerer(_FakeGeminiClient(parsed="Gateway settles on Arc."), model="m")
    assert ans.answer("q", [_src("s1", "Gateway settles on Arc.")]) == "Gateway settles on Arc."


def test_answerer_falls_back_on_error() -> None:
    ans = GeminiAnswerer(_FakeGeminiClient(raises=RuntimeError("boom")), model="m")
    out = ans.answer("Gateway", [_src("s1", "Gateway settles on Arc. It is sub-cent.")])
    assert out  # extractive fallback produced something
    assert "Arc" in out


def test_answerer_no_sources() -> None:
    ans = GeminiAnswerer(_FakeGeminiClient(parsed="x"), model="m")
    assert "No sources" in ans.answer("q", [])


# --- Factory wiring ---------------------------------------------------------


def test_factory_uses_heuristics_without_key() -> None:
    cfg = Settings(gemini_api_key="")
    assert isinstance(build_judge(cfg), HeuristicJudge)
    assert isinstance(build_answerer(cfg), ExtractiveAnswerer)
    assert isinstance(build_scorer(cfg).judge, HeuristicJudge)


def test_factory_uses_gemini_with_key() -> None:
    cfg = Settings(gemini_api_key="g-test")
    assert isinstance(build_judge(cfg), GeminiJudge)
    assert isinstance(build_answerer(cfg), GeminiAnswerer)
    assert isinstance(build_scorer(cfg).judge, GeminiJudge)


# --- Transient-error retry (rate-limit / 5xx resilience) --------------------


def test_judge_retries_transient_then_succeeds() -> None:
    parsed = _JudgeOutput(
        claims=[_ClaimVerdict(claim="Gateway batches USDC", verdict=Verdict.SUPPORTED)],
        rationale="supported",
    )
    client = _FakeGeminiClient(parsed=parsed, fail_times=2)  # two 503s, then success
    judge = GeminiJudge(client, model="m", max_retries=3, sleep=lambda _: None)
    jr = judge.judge(ANSWER, SOURCE)
    assert jr.verdict is Verdict.SUPPORTED  # recovered via retry, not the fallback
    assert client.models.calls == 3  # 2 failures + 1 success


def test_judge_gives_up_after_retries_and_falls_back() -> None:
    client = _FakeGeminiClient(fail_times=99)  # always transient
    judge = GeminiJudge(client, model="m", max_retries=2, sleep=lambda _: None)
    jr = judge.judge(ANSWER, SOURCE)
    assert jr.rationale.startswith("[fallback:heuristic]")
    assert client.models.calls == 3  # initial + 2 retries, then degrade


def test_answerer_retries_transient_then_succeeds() -> None:
    client = _FakeGeminiClient(parsed="Gateway settles on Arc.", fail_times=1)
    ans = GeminiAnswerer(client, model="m", max_retries=3, sleep=lambda _: None)
    assert ans.answer("q", [_src("s1", "x")]) == "Gateway settles on Arc."
    assert client.models.calls == 2


def test_retry_helper_does_not_retry_permanent_errors() -> None:
    # A 400 (permanent) must propagate immediately — no wasted retries.
    calls = {"n": 0}

    def boom() -> None:
        calls["n"] += 1
        raise _TransientError(400)  # 400 is NOT in the retryable set

    with pytest.raises(_TransientError):
        call_with_retry(
            boom, max_retries=5, backoff_base=0.0, backoff_cap=0.0, sleep=lambda _: None
        )
    assert calls["n"] == 1
