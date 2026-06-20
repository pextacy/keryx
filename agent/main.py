"""Agent FastAPI app (CC-B).

Run: ``uvicorn agent.main:app --reload``

POST /ask runs the full citation loop against the MockRail (Phase 2 / M1). At M2 the
MockRail is swapped for CC-A's real settle() with no other change. The agent signs
every answer with an attestation; if no agent key is configured one is generated at
startup so /ask works out of the box (set KERYX_AGENT_PRIVATE_KEY for a stable identity).
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

from eth_account import Account
from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator

from agent.attestation import AttestationSigner, verify_attestation
from agent.factory import (
    build_answerer,
    build_chain_reader,
    build_circle_wallets,
    build_embedder,
    build_erc8004,
    build_erc8183,
    build_ledger,
    build_scorer,
)
from agent.grounding.embeddings import VoyageEmbedder
from agent.ledger_verify import annotate_recent
from agent.llm import llm_enabled
from agent.pipeline import AskPipeline, Session
from registry.factory import build_store
from shared.config import settings
from shared.rail import HttpRail, MockRail, Rail
from shared.splits import Contributor, split_payout
from shared.types import CitationIntent, SettlementStatus


def build_rail() -> Rail:
    """Select the settlement rail from config — MockRail (default) or the real HttpRail.

    The M1->M2 swap is now configuration (``KERYX_RAIL=http``), not a code edit.
    """
    if settings.rail.lower() == "http":
        return HttpRail(settings.payer_url)
    return MockRail()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    # Release long-lived pooled clients on shutdown (idempotent, no-ops when offline).
    if isinstance(_embedder, VoyageEmbedder):
        _embedder.close()
    if _chain_reader is not None:
        _chain_reader.close()
    if _erc8004 is not None:
        _erc8004.close()
    if _erc8183 is not None:
        _erc8183.close()
    if _circle is not None:
        _circle.close()


app = FastAPI(
    title="Keryx Agent",
    version="0.1.0",
    summary="Research agent + grounding verifier + attestation (CC-B)",
    lifespan=lifespan,
)

# Rail comes from config: MockRail by default, HttpRail when KERYX_RAIL=http (Phase 3 / M2).
# Store + ledger are Neon-backed when KERYX_DATABASE_URL is set, else in-memory (default).
rail: Rail = build_rail()
registry = build_store(settings)
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
ledger = build_ledger(settings)
# Chain reader for verifiable /ledger; None (default) -> mirror response, no RPC reads.
_chain_reader = build_chain_reader(settings)
# ERC-8004 identity/reputation client; None (default) -> endpoints report disabled, no RPC.
_erc8004 = build_erc8004(settings)
# ERC-8183 job-escrow client; None (default) -> /job reports disabled, no RPC.
_erc8183 = build_erc8183(settings)
# Circle W3S wallets client; None (default) -> /circle endpoints report disabled, no network.
_circle = build_circle_wallets(settings)


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
    agent_wallet: str | None = Field(
        default=None,
        description="Paying agent wallet; defaults to this agent. Distinct wallets are "
        "counted as distinct sessions in /metrics.",
    )


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
        agent_wallet=req.agent_wallet or signer.address,
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


@app.get("/identity")
def identity() -> dict[str, Any]:
    """The agent's ERC-8004 on-chain identity (opt-in; KERYX_ERC8004_ENABLED).

    Ties the attestation pubkey to a registered agent. Disabled by default (no RPC reads);
    degrades to ``registered: false`` if the agent has not registered or RPC is unreachable.
    """
    if _erc8004 is None:
        return {"enabled": False, "agent_address": signer.address}
    try:
        ident = _erc8004.identity(signer.address)
    except Exception as exc:  # noqa: BLE001 — never 500 on a flaky RPC
        return {"enabled": True, "agent_address": signer.address, "error": type(exc).__name__}
    if ident is None:
        return {"enabled": True, "agent_address": signer.address, "registered": False}
    return {
        "enabled": True,
        "agent_address": signer.address,
        "registered": True,
        "agent_id": ident.agent_id,
        "owner": ident.owner,
        "metadata_uri": ident.metadata_uri,
    }


class ReputationRequest(BaseModel):
    agent_id: int = Field(ge=0, description="ERC-8004 agent id of the author/agent being rated")
    g: float = Field(ge=0.0, le=1.0, description="Grounding score -> reputation (round(100*g))")
    tag: str = Field(default="keryx_grounded_citation")


@app.post("/reputation")
def reputation(req: ReputationRequest) -> dict[str, Any]:
    """Record grounding-derived reputation on-chain (opt-in; requires a signing key).

    Keryx rates as an external verifier (ERC-8004 forbids self-rating). Returns the tx hash.
    """
    if _erc8004 is None:
        return {"enabled": False, "recorded": False, "reason": "erc8004 disabled"}
    if not _erc8004.can_write:
        return {"enabled": True, "recorded": False, "reason": "no agent signing key configured"}
    tx_hash = _erc8004.give_feedback(req.agent_id, g=req.g, tag=req.tag)
    return {"enabled": True, "recorded": True, "agent_id": req.agent_id, "tx_hash": tx_hash}


@app.get("/validation/{request_hash}")
def validation(request_hash: str) -> dict[str, Any]:
    """Read an ERC-8004 ValidationRegistry status (opt-in; KERYX_ERC8004_ENABLED).

    Lets clients audit whether a verifier validated an agent's grounding claim on-chain
    (100=passed / 0=failed). Disabled by default; a flaky RPC or malformed hash degrades to
    an ``error`` field rather than a 500.
    """
    if _erc8004 is None:
        return {"enabled": False}
    try:
        status = _erc8004.validation_status(request_hash)
    except Exception as exc:  # noqa: BLE001 — never 500 on a flaky RPC or bad hash
        return {"enabled": True, "request_hash": request_hash, "error": type(exc).__name__}
    if status is None:
        return {"enabled": True, "request_hash": request_hash, "found": False}
    return {
        "enabled": True,
        "request_hash": request_hash,
        "found": True,
        "validator": status.validator,
        "agent_id": status.agent_id,
        "response": status.response,
        "passed": status.passed,
        "tag": status.tag,
        "last_update": status.last_update,
    }


@app.get("/job/{job_id}")
def job(job_id: int) -> dict[str, Any]:
    """Read an ERC-8183 AgenticCommerce job's on-chain state (opt-in; KERYX_ERC8183_ENABLED).

    A research/citation job with USDC escrow: status moves Open->Funded->Submitted->Completed
    as the agent (provider) delivers. Disabled by default; a flaky RPC degrades to ``error``.
    """
    if _erc8183 is None:
        return {"enabled": False}
    try:
        j = _erc8183.get_job(job_id)
    except Exception as exc:  # noqa: BLE001 — never 500 on a flaky RPC
        return {"enabled": True, "job_id": job_id, "error": type(exc).__name__}
    if j is None:
        return {"enabled": True, "job_id": job_id, "found": False}
    return {
        "enabled": True,
        "job_id": j.id,
        "found": True,
        "client": j.client,
        "provider": j.provider,
        "evaluator": j.evaluator,
        "description": j.description,
        "budget_usdc": str(j.budget),
        "expired_at": j.expired_at,
        "status": j.status.name,
        "hook": j.hook,
    }


@app.get("/circle/transaction/{tx_id}")
def circle_transaction(tx_id: str) -> dict[str, Any]:
    """Read a Circle W3S transaction's status (opt-in; KERYX_CIRCLE_API_KEY).

    Lets the agent track a wallet-provisioned tx (e.g. ERC-8004 register / ERC-8183 fund)
    submitted via Circle. Disabled by default; a flaky API degrades to an ``error`` field.
    """
    if _circle is None:
        return {"enabled": False}
    try:
        tx = _circle.get_transaction(tx_id)
    except Exception as exc:  # noqa: BLE001 — never 500 on a flaky upstream
        return {"enabled": True, "tx_id": tx_id, "error": type(exc).__name__}
    return {"enabled": True, "tx_id": tx_id, "transaction": tx}


_HEX_WALLET = re.compile(r"^0x[0-9a-fA-F]{40}$")


class PayoutRecipient(BaseModel):
    wallet: str = Field(description="0x-prefixed Arc/EVM wallet")
    share: Decimal = Field(gt=0, description="Relative weight from the attribution graph")

    @field_validator("wallet")
    @classmethod
    def _check_wallet(cls, v: str) -> str:
        if not _HEX_WALLET.match(v):
            raise ValueError(f"invalid wallet: {v!r}")
        return v


class PayoutRequest(BaseModel):
    amount: Decimal = Field(gt=0, description="Total USDC to split across contributors")
    contributors: list[PayoutRecipient] = Field(min_length=1)


@app.post("/payout")
def payout(req: PayoutRequest) -> dict[str, Any]:
    """Split one payment across all credited contributors and settle each share (Prior Art 04).

    The attribution graph (writer/editor/photographer weights) in -> proportional on-chain
    splits out, summing exactly to the total with no dust. Settles through the active rail.
    """
    pairs = split_payout(req.amount, [Contributor(c.wallet, c.share) for c in req.contributors])
    intents = [
        CitationIntent(source_id=f"payout:{i}", author_wallet=c.wallet, amount=amt)
        for i, (c, amt) in enumerate(pairs)
        if amt > 0
    ]
    receipts = rail.settle(intents) if intents else []
    rc_by_id = {r.source_id: r for r in receipts}
    recipients: list[dict[str, Any]] = []
    total_settled = Decimal(0)
    for i, (c, amt) in enumerate(pairs):
        rc = rc_by_id.get(f"payout:{i}")
        settled = rc is not None and rc.status is SettlementStatus.SETTLED and bool(rc.tx_hash)
        if settled and rc is not None:
            total_settled += amt
        recipients.append(
            {
                "wallet": c.wallet,
                "share": str(c.weight),
                "amount": str(amt),
                "settled": settled,
                "tx_hash": rc.tx_hash if (settled and rc is not None) else None,
            }
        )
    return {
        "amount": str(req.amount),
        "recipients": recipients,
        "total_settled": str(total_settled),
    }


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    """Traction metrics — the numbers we lead with (prd.md §8)."""
    return ledger.metrics()


@app.get("/ledger")
def get_ledger(limit: int = 50) -> dict[str, Any]:
    """Settlement ledger for the dashboard. Mirrors chain; chain stays canonical.

    When KERYX_LEDGER_VERIFY_CHAIN is on, each recent row is confirmed against Arc and the
    response carries on-chain amounts + a reconciliation summary ("don't trust our DB").
    """
    recent = ledger.recent(limit)
    if _chain_reader is None:
        return {"metrics": ledger.metrics(), "recent": recent, "chain_verified": False}
    annotated = annotate_recent(_chain_reader, recent)
    return {
        "metrics": ledger.metrics(),
        "recent": annotated["entries"],
        "chain_verified": True,
        "verification": {
            "verified_count": annotated["verified_count"],
            "reconciled_usdc": annotated["reconciled_usdc"],
            "source": annotated["source"],
        },
    }
