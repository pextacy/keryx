"""Judge signal for grounding — does the source actually support the answer's claims?

prd.md §6: an LLM judge returns ``supported | partial | unsupported`` per claim with a
rationale. Behind a ``Judge`` protocol so we can run offline (``HeuristicJudge``) in
tests/CI and swap in ``AnthropicJudge`` when an API key is present — same interface.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel

from agent.grounding.embeddings import _tokenize

if TYPE_CHECKING:
    from anthropic import Anthropic

log = logging.getLogger("keryx.grounding.judge")


class Verdict(enum.StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"

    @property
    def score(self) -> float:
        return {"supported": 1.0, "partial": 0.5, "unsupported": 0.0}[self.value]


@dataclass(frozen=True)
class JudgeResult:
    verdict: Verdict
    rationale: str
    per_claim: tuple[tuple[str, Verdict], ...] = field(default_factory=tuple)

    @property
    def score(self) -> float:
        if self.per_claim:
            return sum(v.score for _, v in self.per_claim) / len(self.per_claim)
        return self.verdict.score


@runtime_checkable
class Judge(Protocol):
    def judge(self, answer: str, source_text: str) -> JudgeResult: ...


def _split_claims(answer: str) -> list[str]:
    parts = [s.strip() for s in answer.replace("\n", " ").split(".")]
    return [p for p in parts if p]


class HeuristicJudge:
    """Offline judge: per-claim lexical coverage by the source.

    coverage >= ``supported_at`` -> supported; >= ``partial_at`` -> partial; else
    unsupported. Defensible v1 (prd.md non-goal #6: a v1 heuristic + LLM judge is fine).
    """

    def __init__(self, supported_at: float = 0.6, partial_at: float = 0.3) -> None:
        self.supported_at = supported_at
        self.partial_at = partial_at

    def _coverage(self, claim: str, source_tokens: set[str]) -> float:
        toks = [t for t in _tokenize(claim) if len(t) > 2]
        if not toks:
            return 0.0
        hits = sum(1 for t in toks if t in source_tokens)
        return hits / len(toks)

    def judge(self, answer: str, source_text: str) -> JudgeResult:
        source_tokens = set(_tokenize(source_text))
        per_claim: list[tuple[str, Verdict]] = []
        for claim in _split_claims(answer):
            cov = self._coverage(claim, source_tokens)
            if cov >= self.supported_at:
                v = Verdict.SUPPORTED
            elif cov >= self.partial_at:
                v = Verdict.PARTIAL
            else:
                v = Verdict.UNSUPPORTED
            per_claim.append((claim, v))

        if not per_claim:
            return JudgeResult(Verdict.UNSUPPORTED, "no claims extracted from answer")

        avg = sum(v.score for _, v in per_claim) / len(per_claim)
        overall = (
            Verdict.SUPPORTED
            if avg >= 0.75
            else Verdict.PARTIAL
            if avg >= 0.25
            else Verdict.UNSUPPORTED
        )
        n_sup = sum(1 for _, v in per_claim if v is Verdict.SUPPORTED)
        rationale = f"{n_sup}/{len(per_claim)} claims supported by source (lexical coverage)"
        return JudgeResult(overall, rationale, tuple(per_claim))


# --- LLM judge (production) -------------------------------------------------

_JUDGE_SYSTEM = (
    "You are a citation grounding verifier. Given an ANSWER produced by a research "
    "agent and one candidate SOURCE passage, decide, for each distinct factual claim "
    "in the answer, whether THIS source supports it. Verdicts: 'supported' (the source "
    "directly substantiates the claim), 'partial' (the source is related/consistent but "
    "does not fully substantiate it), 'unsupported' (the source does not address the "
    "claim, or contradicts it). Judge only against the given source — do not use outside "
    "knowledge. Extract the claims yourself; ignore filler. Be strict: a source that is "
    "merely on the same topic is 'partial', not 'supported'."
)


class _ClaimVerdict(BaseModel):
    claim: str
    verdict: Verdict


class _JudgeOutput(BaseModel):
    claims: list[_ClaimVerdict]
    rationale: str


def _overall(per_claim: list[tuple[str, Verdict]]) -> Verdict:
    avg = sum(v.score for _, v in per_claim) / len(per_claim)
    if avg >= 0.75:
        return Verdict.SUPPORTED
    return Verdict.PARTIAL if avg >= 0.25 else Verdict.UNSUPPORTED


class AnthropicJudge:
    """Claude-backed grounding judge — the production moat (prd.md §6).

    Asks Claude for per-claim ``supported|partial|unsupported`` verdicts via structured
    outputs, then folds them into the same ``JudgeResult`` the heuristic judge returns,
    so the scorer is agnostic to which judge ran. Resilient by design: any API/parse
    failure degrades to ``fallback`` (the offline heuristic) rather than breaking the
    citation loop, and the rationale records which judge actually decided.
    """

    def __init__(
        self,
        client: Anthropic,
        *,
        model: str,
        effort: str = "low",
        max_tokens: int = 4096,
        fallback: Judge | None = None,
    ) -> None:
        self._client = client
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.fallback: Judge = fallback or HeuristicJudge()

    def judge(self, answer: str, source_text: str) -> JudgeResult:
        if not answer.strip() or not source_text.strip():
            return JudgeResult(Verdict.UNSUPPORTED, "empty answer or source")
        client: Any = self._client  # SDK call is an untyped boundary; guarded by except
        try:
            resp = client.messages.parse(
                model=self.model,
                max_tokens=self.max_tokens,
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort},
                system=_JUDGE_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"ANSWER:\n{answer}\n\n"
                            f"SOURCE:\n{source_text}\n\n"
                            "Return the per-claim verdicts and a one-sentence rationale."
                        ),
                    }
                ],
                output_format=_JudgeOutput,
            )
            parsed = resp.parsed_output
        except Exception as exc:  # noqa: BLE001 — any failure degrades to the heuristic
            log.warning("AnthropicJudge fell back to heuristic: %s", exc)
            jr = self.fallback.judge(answer, source_text)
            return JudgeResult(jr.verdict, f"[fallback:heuristic] {jr.rationale}", jr.per_claim)

        if parsed is None or not parsed.claims:
            return JudgeResult(Verdict.UNSUPPORTED, "judge returned no claims")
        per_claim = [(c.claim, c.verdict) for c in parsed.claims]
        rationale = f"[claude:{self.model}] {parsed.rationale}"
        return JudgeResult(_overall(per_claim), rationale, tuple(per_claim))
