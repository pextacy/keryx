"""The citation loop — retrieve -> answer -> ground -> settle -> attest.

Orchestrates prd.md §5 against any ``Rail`` (MockRail now, CC-A's real settle() at M2).
The agent *decides*: which sources grounded the answer (g >= T), which to pay, and when
budget is spent — agentic, not a meter. Every answer carries >=1 cited and >=1
evaluated-but-not-cited source so the gating is visible and honest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

from agent.answerer import Answerer, ExtractiveAnswerer
from agent.attestation import AttestationSigner
from agent.grounding.embeddings import Embedder
from agent.grounding.scorer import GroundingResult, GroundingScorer
from agent.retrieval import retrieve
from registry.store import SourceStore
from shared.rail import Rail
from shared.types import (
    USDC_DECIMALS,
    USDC_FLOOR,
    Attestation,
    CitationIntent,
    CitationRecord,
    SettlementStatus,
)

# Smallest representable USDC unit; used to clamp a client-supplied per-source cap to a
# valid amount before it reaches CitationIntent's stricter validator.
_USDC_QUANTUM = Decimal(1).scaleb(-USDC_DECIMALS)


@dataclass
class Session:
    """A paying-agent session: funded wallet, budget, per-source cap."""

    agent_wallet: str
    budget_total: Decimal = Decimal("1")
    budget_spent: Decimal = Decimal(0)
    per_source_cap: Decimal | None = None

    @property
    def remaining(self) -> Decimal:
        return self.budget_total - self.budget_spent


@dataclass(frozen=True)
class AskResult:
    answer: str
    citations: tuple[CitationRecord, ...]
    attestation: Attestation
    total_settled: Decimal
    grounding: tuple[GroundingResult, ...] = field(default_factory=tuple)

    @property
    def cited(self) -> list[CitationRecord]:
        return [c for c in self.citations if c.cited]

    @property
    def evaluated_not_cited(self) -> list[CitationRecord]:
        return [c for c in self.citations if not c.cited]


class AskPipeline:
    def __init__(
        self,
        *,
        store: SourceStore,
        rail: Rail,
        signer: AttestationSigner,
        scorer: GroundingScorer | None = None,
        answerer: Answerer | None = None,
        embedder: Embedder | None = None,
        k: int = 5,
    ) -> None:
        self.store = store
        self.rail = rail
        self.signer = signer
        self.scorer = scorer or GroundingScorer()
        self.answerer = answerer or ExtractiveAnswerer()
        # Same embedder as the scorer so retrieval and grounding share one embedding space
        # (and one cache). None -> retrieval uses the BagOfWords default, like the scorer.
        self.embedder = embedder
        self.k = k

    def ask(self, query: str, session: Session) -> AskResult:
        candidates = retrieve(query, self.store, k=self.k, embedder=self.embedder)
        answer = self.answerer.answer(query, candidates)

        by_id = {s.source_id: s for s in candidates}
        results = [
            self.scorer.score(source_id=s.source_id, answer=answer, source_text=s.text)
            for s in candidates
        ]

        # Decide what to pay: grounded (g>=T) + has a payee + fits budget/cap.
        intents: list[CitationIntent] = []
        skip_reason: dict[str, str] = {}
        for r in sorted(results, key=lambda x: x.g, reverse=True):
            src = by_id[r.source_id]
            if not r.cited:
                continue  # below T — evaluated, not cited
            if not src.payable:
                skip_reason[r.source_id] = "grounded but no author wallet in registry"
                continue
            cap = session.per_source_cap
            amount = min(r.amount, cap) if cap is not None else r.amount
            # A client-supplied cap can carry sub-micro precision; round down to the USDC
            # quantum so the intent is constructible, and skip (don't crash) if the capped
            # toll falls below the floor — a cap below 0.000001 means "too small to pay".
            amount = amount.quantize(_USDC_QUANTUM, rounding=ROUND_DOWN)
            if amount < USDC_FLOOR:
                skip_reason[r.source_id] = "grounded but per-source cap below USDC floor"
                continue
            if amount > session.remaining - sum(i.amount for i in intents):
                skip_reason[r.source_id] = "grounded but session budget exhausted"
                continue
            assert src.author_wallet is not None  # guaranteed by src.payable above
            intents.append(
                CitationIntent(
                    source_id=r.source_id,
                    author_wallet=src.author_wallet,
                    amount=amount,
                )
            )

        receipts = self.rail.settle(intents) if intents else []
        receipt_by_id = {rc.source_id: rc for rc in receipts}
        intent_amount = {i.source_id: i.amount for i in intents}

        records: list[CitationRecord] = []
        total = Decimal(0)
        for r in results:
            src = by_id[r.source_id]
            rc = receipt_by_id.get(r.source_id)
            if rc and rc.status is SettlementStatus.SETTLED and rc.tx_hash:
                amt = intent_amount[r.source_id]
                total += amt
                records.append(
                    CitationRecord(
                        source_url=src.url, g=r.g, amount=amt, tx_hash=rc.tx_hash, cited=True
                    )
                )
            else:
                # Below T, unpayable, budget-skipped, or settlement failed -> $0, visible.
                records.append(
                    CitationRecord(source_url=src.url, g=r.g, amount=Decimal(0), cited=False)
                )

        session.budget_spent += total
        attestation = self.signer.build(query=query, answer=answer, citations=records)
        return AskResult(
            answer=answer,
            citations=tuple(records),
            attestation=attestation,
            total_settled=total,
            grounding=tuple(results),
        )
