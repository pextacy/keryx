"""Judge signal for grounding — does the source actually support the answer's claims?

prd.md §6: an LLM judge returns ``supported | partial | unsupported`` per claim with a
rationale. Behind a ``Judge`` protocol so we can run offline (``HeuristicJudge``) in
tests/CI and swap in ``AnthropicJudge`` when an API key is present — same interface.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from agent.grounding.embeddings import _tokenize


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
