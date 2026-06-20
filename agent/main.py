"""Agent FastAPI app (CC-B).

Run: ``uvicorn agent.main:app --reload``

POST /ask runs the full citation loop against the MockRail (Phase 2 / M1). At M2 the
MockRail is swapped for CC-A's real settle() with no other change. The agent signs
every answer with an attestation; if no agent key is configured one is generated at
startup so /ask works out of the box (set KERYX_AGENT_PRIVATE_KEY for a stable identity).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

from eth_account import Account
from fastapi import FastAPI
from pydantic import BaseModel, Field

from agent.attestation import AttestationSigner, verify_attestation
from agent.factory import build_answerer, build_embedder, build_scorer
from agent.grounding.embeddings import VoyageEmbedder
from agent.ledger import Ledger
from agent.llm import llm_enabled
from agent.pipeline import AskPipeline, Session
from registry.fixtures import seeded_registry
from shared.config import settings
from shared.rail import MockRail, Rail


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    # Release the long-lived pooled Voyage client on shutdown (idempotent, no-op offline).
    if isinstance(_embedder, VoyageEmbedder):
        _embedder.close()


app = FastAPI(
    title="Keryx Agent",
    version="0.1.0",
    summary="Research agent + grounding verifier + attestation (CC-B)",
    lifespan=lifespan,
)

# Phase 2: mock rail + offline seeded registry. Phase 3 swaps in the real settle().
rail: Rail = MockRail()
registry = seeded_registry()
_agent_key = settings.agent_private_key or Account.create().key.hex()
signer = AttestationSigner(_agent_key)
# Real Claude judge + answerer when KERYX_ANTHROPIC_API_KEY is set; heuristics otherwise.
# Dense Voyage embedder when KERYX_VOYAGE_API_KEY is set; offline BagOfWords otherwise.
# One embedder instance feeds both scoring and retrieval so they share an embedding space.
_embedder = build_embedder(settings)
pipeline = AskPipeline(
    store=registry,
    rail=rail,
    signer=signer,
    scorer=build_scorer(settings, embedder=_embedder),
    answerer=build_answerer(settings),
    embedder=_embedder,
)
ledger = Ledger()


def _embedder_status() -> dict[str, Any]:
    """Live effective similarity path — dense only when keyed AND not degraded."""
    dense = isinstance(_embedder, VoyageEmbedder) and not _embedder.is_degraded
    degraded = isinstance(_embedder, VoyageEmbedder) and _embedder.is_degraded
    return {
        "embedder": "VoyageEmbedder" if dense else "BagOfWordsEmbedder",
        "embedding_model": settings.embedding_model if dense else None,
        "embedder_degraded": degraded,
        "embedder_stats": _embedder.stats() if isinstance(_embedder, VoyageEmbedder) else None,
    }


class AskRequest(BaseModel):
    query: str = Field(min_length=1)
    budget: Decimal | None = Field(default=None, description="USDC budget for this query")
    per_source_cap: Decimal | None = None
    external: bool = Field(default=False, description="True if from a non-team agent")


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    status = _embedder_status()
    return {
        "status": "ok",
        "service": "agent",
        "rail": type(rail).__name__,
        "llm": llm_enabled(settings),
        "embedder": status["embedder"],
        "embedder_degraded": status["embedder_degraded"],
    }


@app.get("/config")
def config() -> dict[str, Any]:
    enabled = llm_enabled(settings)
    return {
        "grounding_threshold": settings.grounding_threshold,
        "rail": type(rail).__name__,
        "agent_pubkey": signer.address,
        "sources_indexed": len(registry.all()),
        # Which grounding/answer path is live — Claude when a key is set, else heuristic.
        "llm_enabled": enabled,
        "judge": type(pipeline.scorer.judge).__name__,
        "answerer": type(pipeline.answerer).__name__,
        "judge_model": settings.judge_model if enabled else None,
        "answer_model": settings.answer_model_resolved if enabled else None,
        # Which similarity path is live — dense Voyage when keyed AND healthy, else BagOfWords.
        **_embedder_status(),
    }


@app.post("/ask")
def ask(req: AskRequest) -> dict[str, Any]:
    session = Session(
        agent_wallet=signer.address,
        budget_total=req.budget if req.budget is not None else Decimal("1"),
        per_source_cap=req.per_source_cap,
    )
    result = pipeline.ask(req.query, session)
    author_wallets = {s.url: s.author_wallet for s in registry.all()}
    ledger.record(
        query_hash=result.attestation.query_hash,
        agent_wallet=session.agent_wallet,
        citations=list(result.citations),
        author_wallets=author_wallets,
        external=req.external,
    )
    return {
        "answer": result.answer,
        "total_settled": str(result.total_settled),
        "citations": [
            {
                "source_url": c.source_url,
                "g": c.g,
                "amount": str(c.amount),
                "tx_hash": c.tx_hash,
                "cited": c.cited,
            }
            for c in result.citations
        ],
        "counts": {
            "cited": len(result.cited),
            "evaluated_not_cited": len(result.evaluated_not_cited),
        },
        "attestation": {
            "query_hash": result.attestation.query_hash,
            "answer_hash": result.attestation.answer_hash,
            "agent_pubkey": result.attestation.agent_pubkey,
            "ts": result.attestation.ts,
            "signature": result.attestation.signature,
            "verified": verify_attestation(result.attestation),
        },
    }


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    """Traction metrics — the numbers we lead with (prd.md §8)."""
    return ledger.metrics()


@app.get("/ledger")
def get_ledger(limit: int = 50) -> dict[str, Any]:
    """Settlement ledger for the dashboard. Mirrors chain; chain stays canonical."""
    return {"metrics": ledger.metrics(), "recent": ledger.recent(limit)}
