"""The grounding gate — combine signals into g, decide payment, size the amount.

This is the moat (docs.md): similarity + judge -> grounding score ``g in [0,1]``;
pay only if ``g >= T``; amount is the per-citation toll, optionally scaled by g so a
source that grounded more earns more (prd.md §6 innovation hook).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from agent.grounding.embeddings import Embedder, similarity
from agent.grounding.judge import HeuristicJudge, Judge, JudgeResult
from shared.config import Settings, settings
from shared.types import USDC_DECIMALS


@dataclass(frozen=True)
class GroundingResult:
    """Per-source grounding outcome — the audit record behind a pay/skip decision."""

    source_id: str
    similarity: float
    judge: JudgeResult
    g: float
    cited: bool  # g >= T
    amount: Decimal  # toll if cited, else 0
    rationale: str


def _quantize(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal(1).scaleb(-USDC_DECIMALS), rounding=ROUND_DOWN)


class GroundingScorer:
    """Scores a candidate source against an answer and applies the settlement gate."""

    def __init__(
        self,
        *,
        config: Settings | None = None,
        embedder: Embedder | None = None,
        judge: Judge | None = None,
    ) -> None:
        self.cfg = config or settings
        self.embedder = embedder
        self.judge: Judge = judge or HeuristicJudge()
        total = self.cfg.similarity_weight + self.cfg.judge_weight
        # Normalize weights so g stays in [0,1] regardless of configured magnitudes.
        self._w_sim = self.cfg.similarity_weight / total if total else 0.5
        self._w_judge = self.cfg.judge_weight / total if total else 0.5

    def amount_for(self, g: float) -> Decimal:
        """Per-citation toll for a grounded source.

        Flat ``citation_toll_min`` by default; if ``scale_amount_by_g`` is set, scale
        linearly across the [min, max] toll band by g (never below floor).
        """
        g = max(0.0, min(1.0, g))  # clamp so the toll never escapes the [min, max] band
        lo, hi = self.cfg.citation_toll_min, self.cfg.citation_toll_max
        amount = lo + (hi - lo) * Decimal(str(g)) if self.cfg.scale_amount_by_g else lo
        amount = max(amount, self.cfg.usdc_floor)
        return _quantize(amount)

    def score(self, *, source_id: str, answer: str, source_text: str) -> GroundingResult:
        sim = similarity(answer, source_text, self.embedder)
        jr = self.judge.judge(answer, source_text)
        g = self._w_sim * sim + self._w_judge * jr.score
        # Round once, then gate and record on the SAME value — so a displayed g can
        # never read >= T while the source was left uncited (or vice versa).
        g = round(max(0.0, min(1.0, g)), 4)
        cited = g >= self.cfg.grounding_threshold
        amount = self.amount_for(g) if cited else Decimal(0)
        gate = ">=" if cited else "<"
        rationale = (
            f"sim={sim:.2f}*{self._w_sim:.2f} + judge={jr.score:.2f}*{self._w_judge:.2f} "
            f"=> g={g:.2f} {gate} T={self.cfg.grounding_threshold}. {jr.rationale}"
        )
        return GroundingResult(
            source_id=source_id,
            similarity=sim,
            judge=jr,
            g=g,
            cited=cited,
            amount=amount,
            rationale=rationale,
        )
