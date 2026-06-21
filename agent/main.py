"""Agent FastAPI app (CC-B).

Run: ``uvicorn agent.main:app --reload``

POST /ask runs the full citation loop against the MockRail (Phase 2 / M1). At M2 the
MockRail is swapped for CC-A's real settle() with no other change. The agent signs
every answer with an attestation; if no agent key is configured one is generated at
startup so /ask works out of the box (set KERYX_AGENT_PRIVATE_KEY for a stable identity).
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any, Literal

from eth_account import Account
from fastapi import FastAPI, Request
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
from shared.bonds import BondAlreadyResolved, BondBook, BondStatus
from shared.config import settings
from shared.credits import CreditBook, CreditError
from shared.gateway import SUPPORTED_CHAINS, GatewayBook, GatewayError, normalize_chain
from shared.memo import Memo, build_memo
from shared.p2p import RequestBook, RequestError
from shared.qf import Project, quadratic_match
from shared.rail import HttpRail, MockRail, Rail
from shared.splits import Contributor, split_payout
from shared.streaming import StreamBook, StreamClosed
from shared.swap import SwapError
from shared.swap import quote as swap_quote
from shared.traction import TractionBook
from shared.treasury import Treasury, TreasuryError
from shared.types import Attestation, CitationIntent, SettlementStatus
from shared.workflow import WorkflowError, WorkflowManager


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
    openapi_tags=[
        {"name": "research", "description": "Ask + grounded citations + attestation audit."},
        {"name": "primitives", "description": "Nanopayment primitives that settle via the rail."},
        {"name": "on-chain", "description": "Opt-in ERC-8004 / ERC-8183 / Circle reads + writes."},
        {"name": "ledger-ops", "description": "Ledger, traction, reconciliation, memos, demo."},
        {"name": "ops", "description": "Health, config, status."},
    ],
)

log = logging.getLogger("keryx.agent")


@app.middleware("http")
async def _request_log(request: Request, call_next: Any) -> Any:
    """Tag each request with an id and log method/path/status/latency (observability)."""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    response.headers["X-Request-ID"] = request_id
    log.info(
        "%s %s -> %d (%.1fms) rid=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    return response


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
# Reputation bonds (PA 08): in-memory book; a slash settles to the claimant via the rail.
bonds = BondBook()
# Streaming payments (RFB 4): each tick settles the newly-accrued micro-USDC via the rail.
streams = StreamBook()
# Traction: rolls up settled volume across every primitive (the 30%-weighted judging axis).
traction = TractionBook()
# Provenance memos attached to settlements (tx_hash -> one-line memo). On-chain this is the
# transfer memo field (Arc "Send USDC with a memo" / circlefin/recibo); here it travels with
# the receipt. ``_memo_meta`` holds the structured recibo-style envelope (kind/ref/note/routing).
_memos: dict[str, str] = {}
_memo_objs: dict[str, Memo] = {}


def _record_memo(tx_hash: str, memo: Memo) -> None:
    """Bind a structured provenance memo to a settlement tx (plaintext line + envelope).

    The Memo object is kept so reads can redact a confidential note in public feeds while a
    direct read returns it in full. ``line()`` already redacts, so ``_memos`` is feed-safe.
    """
    line = memo.line()
    if line:
        _memos[tx_hash] = line
    _memo_objs[tx_hash] = memo


# Refundable sends (tx_hash -> {to, amount, refunded}) for the dispute/refund flow
# (inspired by circlefin/refund-protocol — stablecoin payment disputes).
_sends: dict[str, dict[str, Any]] = {}
# Approved-action workflows (ported from circlefin/circle-ooak): a batch of settlement
# intents is approved once, then executed in order — nothing settles that wasn't approved.
_workflows = WorkflowManager()
# Split-bill money requests (inspired by circlefin/arc-p2p-payments): a payee requests a
# total split across payers; each payer's share settles to the payee on fulfil.
_requests = RequestBook()
# Prepaid credits (ported from circlefin/arc-commerce): top up USDC once into a balance, then
# draw it down per action — batches many micro-tolls into one settlement.
_credits = CreditBook()
# Gateway unified balance (ported from circlefin/arc-multichain-wallet): deposit USDC from
# multiple source chains into one Arc-spendable balance.
_gateway = GatewayBook()


def _settle_to(source_id: str, wallet: str, amount: Decimal, *, kind: str) -> str | None:
    """Settle one amount to a wallet through the active rail; record traction. None on fail."""
    if amount <= 0:
        return None
    intent = CitationIntent(source_id=source_id, author_wallet=wallet, amount=amount)
    receipts = rail.settle([intent])
    rc = receipts[0] if receipts else None
    if rc is not None and rc.status is SettlementStatus.SETTLED:
        traction.record(kind, amount)
        return rc.tx_hash
    return None


def _demo_wallet(n: int) -> str:
    return "0x" + format(0x1000 + n, "040x")


def _sample_round(seed: int) -> None:
    """Drive one round of every primitive server-side (the /demo/run + UI volume button)."""
    w = _demo_wallet
    for i, (c, amt) in enumerate(
        split_payout(
            Decimal("0.006"),
            [Contributor(w(seed + 1), Decimal(3)), Contributor(w(seed + 2), Decimal(1))],
        )
    ):
        _settle_to(f"demo-payout:{seed}:{i}", c.wallet, amt, kind="payout")
    for i, (c, amt) in enumerate(
        split_payout(
            Decimal("0.004"),
            [Contributor(w(seed + 4), Decimal(8)), Contributor(w(seed + 5), Decimal(2))],
        )
    ):
        _settle_to(f"demo-royalty:{seed}:{i}", c.wallet, amt, kind="royalty")
    for i, (p, match) in enumerate(
        quadratic_match(
            Decimal("0.005"),
            [Project(w(seed + 6), [Decimal(1)] * 4), Project(w(seed + 7), [Decimal(4)])],
        )
    ):
        _settle_to(f"demo-qf:{seed}:{i}", p.wallet, match, kind="qf")
    for i, (p, award) in enumerate(
        quadratic_match(
            Decimal("0.005"),
            [Project(w(seed + 8), [Decimal(1)] * 5), Project(w(seed + 9), [Decimal(1)])],
        )
    ):
        _settle_to(f"demo-retro:{seed}:{i}", p.wallet, award, kind="retro")
    bond = bonds.post(provider=w(seed + 10), amount=Decimal("0.003"), claimant=w(seed + 11))
    bonds.resolve(bond.id, passed=False)
    _settle_to(f"demo-bond:{seed}", bond.claimant, bond.amount, kind="bond")
    stream = streams.open(payer=w(seed), payee=w(seed + 1), rate=Decimal("0.001"))
    billed = streams.tick(stream.id, Decimal(3))
    streams.close(stream.id)
    _settle_to(f"demo-stream:{seed}", stream.payee, billed, kind="stream")
    _sample_ported_round(seed)


def _sample_ported_round(seed: int) -> None:
    """Exercise the vendored-Circle primitives too, so 'generate volume' shows them in traction.

    Swap (arc-stablecoin-fx), split-bill request (arc-p2p-payments), prepaid credits +
    treasury (arc-commerce / arc-fintech), and an approved workflow (circle-ooak) — each
    settles through the rail under its own traction kind.
    """
    w = _demo_wallet
    # Stablecoin swap: settle the net EURC out to a wallet.
    q = swap_quote("USDC", "EURC", Decimal("0.002"), settings.swap_app_fee_bps)
    _settle_to(f"demo-swap:{seed}", w(seed + 12), q.amount_out, kind="swap")
    # Split-bill request: a payee collects from two payers.
    req = _requests.create(w(seed + 13), [w(seed + 14), w(seed + 15)], Decimal("0.004"))
    for share in list(req.shares):
        _requests.fulfil(req.id, share.payer)
        tx = _settle_to(
            f"demo-request:{seed}:{share.payer}", req.payee, share.amount, kind="request"
        )
        if tx is not None:
            _requests.settled(share, tx)
    # Prepaid credits: top up (settles to the treasury) then draw down.
    topup_tx = _settle_to(f"demo-credits:{seed}", _CREDIT_TREASURY, Decimal("0.003"), kind="topup")
    if topup_tx is not None:
        _credits.credit(w(seed + 16), Decimal("0.003"), topup_tx)
        _treasury.deposit(Decimal("0.003"), w(seed + 16), topup_tx)
        _credits.spend(w(seed + 16), Decimal("0.001"), "demo-citation")
    # Approved workflow: approve a one-action batch and execute it in order.
    args: dict[str, object] = {"to": w(seed + 17), "amount": "0.002", "kind": "workflow"}
    wfid = _workflows.approve([{"function": "settle", "args": args}])
    action = _workflows.check(wfid, "settle", args)
    wf_tx = _settle_to(f"demo-workflow:{seed}", w(seed + 17), Decimal("0.002"), kind="workflow")
    _workflows.complete(wfid, action, wf_tx or "", ok=wf_tx is not None)


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


@app.get("/healthz", tags=["ops"])
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


@app.get("/config", tags=["ops"])
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


@app.post("/ask", tags=["research"])
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
                "author_wallet": author_wallets.get(c.source_url),
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


@app.get("/identity", tags=["on-chain"])
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


@app.post("/reputation", tags=["on-chain"])
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


@app.get("/validation/{request_hash}", tags=["on-chain"])
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


@app.get("/job/{job_id}", tags=["on-chain"])
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


@app.get("/circle/transaction/{tx_id}", tags=["on-chain"])
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


@app.post("/payout", tags=["primitives"])
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
            traction.record("payout", amt)
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


class BondRequest(BaseModel):
    provider: str = Field(description="0x wallet of the agent posting the bond")
    claimant: str = Field(description="0x wallet paid if the provider is slashed")
    amount: Decimal = Field(gt=0, description="USDC bond at risk")

    @field_validator("provider", "claimant")
    @classmethod
    def _check_wallet(cls, v: str) -> str:
        if not _HEX_WALLET.match(v):
            raise ValueError(f"invalid wallet: {v!r}")
        return v


class ResolveRequest(BaseModel):
    passed: bool = Field(description="True if the provider delivered (release), else slash")


def _bond_view(b: Any) -> dict[str, Any]:
    return {
        "bond_id": b.id,
        "provider": b.provider,
        "claimant": b.claimant,
        "amount": str(b.amount),
        "status": b.status.value,
        "reputation_delta": b.reputation_delta,
    }


# Far-future expiry for the on-chain escrow anchor (year 2100); the bond resolves long before.
_ESCROW_EXPIRY = 4102444800


def _escrow_anchor(bond: Any) -> dict[str, Any] | None:
    """Best-effort on-chain ERC-8183 escrow backing a bond (opt-in; needs key + funds).

    None when ERC-8183 is disabled or read-only (the offline bond is unchanged). Otherwise
    submits a real createJob tx as proof-of-escrow; any failure degrades to an error field
    rather than breaking the bond. The reference contract releases to the provider on
    complete, so the slash-to-claimant transfer still goes through the rail.
    """
    if _erc8183 is None or not _erc8183.can_write:
        return None
    try:
        tx_hash = _erc8183.create_job(
            provider=bond.provider,
            evaluator=bond.claimant,
            expired_at=_ESCROW_EXPIRY,
            description=f"keryx-bond:{bond.id}",
        )
        return {"tx_hash": tx_hash, "status": "submitted"}
    except Exception as exc:  # noqa: BLE001 — escrow is best-effort; never break the bond
        return {"error": type(exc).__name__}


@app.post("/bond", tags=["primitives"])
def post_bond(req: BondRequest) -> dict[str, Any]:
    """Post a USDC reputation bond standing behind a match (PA 08 / RFB 3).

    When ERC-8183 is enabled with a signing key, the bond is also anchored in a real on-chain
    job escrow (``escrow`` field); otherwise it is the in-memory bond settled via the rail.
    """
    bond = bonds.post(provider=req.provider, amount=req.amount, claimant=req.claimant)
    view = _bond_view(bond)
    anchor = _escrow_anchor(bond)
    if anchor is not None:
        view["escrow"] = anchor
    return view


@app.get("/bond/{bond_id}", tags=["primitives"])
def get_bond(bond_id: str) -> dict[str, Any]:
    bond = bonds.get(bond_id)
    if bond is None:
        return {"found": False, "bond_id": bond_id}
    return {"found": True, **_bond_view(bond)}


@app.post("/bond/{bond_id}/resolve", tags=["primitives"])
def resolve_bond(bond_id: str, req: ResolveRequest) -> dict[str, Any]:
    """Resolve a bond: release to the provider on a pass, or slash to the claimant on a fail.

    A slash settles the bond amount to the wronged claimant through the active rail —
    reputation as capital at risk, not a self-reported score.
    """
    try:
        bond = bonds.resolve(bond_id, passed=req.passed)
    except KeyError:
        return {"found": False, "bond_id": bond_id}
    except BondAlreadyResolved:
        return {"error": "already_resolved", "bond_id": bond_id}

    tx_hash: str | None = None
    if bond.status is BondStatus.SLASHED:
        intent = CitationIntent(
            source_id=f"slash:{bond.id}", author_wallet=bond.claimant, amount=bond.amount
        )
        receipts = rail.settle([intent])
        rc = receipts[0] if receipts else None
        if rc is not None and rc.status is SettlementStatus.SETTLED:
            tx_hash = rc.tx_hash
            traction.record("bond", bond.amount)
    return {**_bond_view(bond), "tx_hash": tx_hash}


class StreamRequest(BaseModel):
    payer: str = Field(description="0x wallet authorizing the flow")
    payee: str = Field(description="0x wallet receiving the stream")
    rate: Decimal = Field(gt=0, description="USDC per second")

    @field_validator("payer", "payee")
    @classmethod
    def _check_wallet(cls, v: str) -> str:
        if not _HEX_WALLET.match(v):
            raise ValueError(f"invalid wallet: {v!r}")
        return v


class TickRequest(BaseModel):
    seconds: Decimal = Field(gt=0, description="Duration of flow to bill")


def _stream_view(s: Any) -> dict[str, Any]:
    return {
        "stream_id": s.id,
        "payer": s.payer,
        "payee": s.payee,
        "rate": str(s.rate),
        "status": s.status.value,
        "total_settled": str(s.settled),
    }


@app.post("/stream", tags=["primitives"])
def open_stream(req: StreamRequest) -> dict[str, Any]:
    """Open a per-second payment stream (RFB 4): approve a rate, bill by the second."""
    s = streams.open(payer=req.payer, payee=req.payee, rate=req.rate)
    return _stream_view(s)


@app.get("/stream/{stream_id}", tags=["primitives"])
def get_stream(stream_id: str) -> dict[str, Any]:
    s = streams.get(stream_id)
    if s is None:
        return {"found": False, "stream_id": stream_id}
    return {"found": True, **_stream_view(s)}


def _tick_response(stream_id: str, billed: Decimal) -> dict[str, Any]:
    s = streams.get(stream_id)
    assert s is not None
    tx_hash = _settle_to(f"stream:{stream_id}:{s.settled}", s.payee, billed, kind="stream")
    return {**_stream_view(s), "billed": str(billed), "tx_hash": tx_hash}


@app.post("/stream/{stream_id}/tick", tags=["primitives"])
def tick_stream(stream_id: str, req: TickRequest) -> dict[str, Any]:
    """Bill ``seconds`` of flow and settle the newly-accrued micro-USDC to the payee."""
    try:
        billed = streams.tick(stream_id, req.seconds)
    except KeyError:
        return {"found": False, "stream_id": stream_id}
    except StreamClosed:
        return {"error": "stream_closed", "stream_id": stream_id}
    return _tick_response(stream_id, billed)


@app.post("/stream/{stream_id}/pause", tags=["primitives"])
def pause_stream(stream_id: str) -> dict[str, Any]:
    try:
        s = streams.pause(stream_id)
    except (KeyError, StreamClosed):
        return {"found": False, "stream_id": stream_id}
    return _stream_view(s)


@app.post("/stream/{stream_id}/resume", tags=["primitives"])
def resume_stream(stream_id: str) -> dict[str, Any]:
    try:
        s = streams.resume(stream_id)
    except (KeyError, StreamClosed):
        return {"found": False, "stream_id": stream_id}
    return _stream_view(s)


@app.post("/stream/{stream_id}/close", tags=["primitives"])
def close_stream(stream_id: str) -> dict[str, Any]:
    """Close the stream and settle any final billable micro-USDC."""
    try:
        _s, billed = streams.close(stream_id)
    except KeyError:
        return {"found": False, "stream_id": stream_id}
    except StreamClosed:
        return {"error": "already_closed", "stream_id": stream_id}
    return _tick_response(stream_id, billed)


class Play(BaseModel):
    wallet: str = Field(description="0x wallet of the creator")
    count: int = Field(ge=0, description="Real plays/citations in the window")

    @field_validator("wallet")
    @classmethod
    def _check_wallet(cls, v: str) -> str:
        if not _HEX_WALLET.match(v):
            raise ValueError(f"invalid wallet: {v!r}")
        return v


class RoyaltiesRequest(BaseModel):
    budget: Decimal = Field(gt=0, description="The listener's budget for the window")
    plays: list[Play] = Field(min_length=1)
    min_count: int = Field(default=1, ge=1, description="Play-gate: fewer plays earn nothing")


@app.post("/royalties", tags=["primitives"])
def royalties(req: RoyaltiesRequest) -> dict[str, Any]:
    """User-centric royalties (PA 05): a listener's budget goes only to the creators they
    actually played, split by real play counts. Play-gating drops sub-threshold engagement —
    a skip in the first seconds costs nothing."""
    eligible = [p for p in req.plays if p.count >= req.min_count]
    gated_out = len(req.plays) - len(eligible)
    if not eligible:
        return {
            "budget": str(req.budget),
            "recipients": [],
            "total_settled": "0",
            "gated_out": gated_out,
        }
    pairs = split_payout(req.budget, [Contributor(p.wallet, Decimal(p.count)) for p in eligible])
    recipients: list[dict[str, Any]] = []
    total_settled = Decimal(0)
    for i, (play, (c, amt)) in enumerate(zip(eligible, pairs, strict=True)):
        tx_hash = _settle_to(f"royalty:{i}", c.wallet, amt, kind="royalty")
        if tx_hash is not None:
            total_settled += amt
        recipients.append(
            {
                "wallet": c.wallet,
                "plays": play.count,
                "amount": str(amt),
                "settled": tx_hash is not None,
                "tx_hash": tx_hash,
            }
        )
    return {
        "budget": str(req.budget),
        "recipients": recipients,
        "total_settled": str(total_settled),
        "gated_out": gated_out,
    }


class QfProject(BaseModel):
    wallet: str = Field(description="0x wallet of the project")
    contributions: list[Decimal] = Field(default_factory=list, description="Backer amounts")

    @field_validator("wallet")
    @classmethod
    def _check_wallet(cls, v: str) -> str:
        if not _HEX_WALLET.match(v):
            raise ValueError(f"invalid wallet: {v!r}")
        return v


class QfRequest(BaseModel):
    pool: Decimal = Field(gt=0, description="Match pool to distribute")
    projects: list[QfProject] = Field(min_length=1)


@app.post("/qf", tags=["primitives"])
def qf(req: QfRequest) -> dict[str, Any]:
    """Quadratic-funding match (PA 03/07): distribute a pool by breadth of support — a
    project backed by many small contributions beats one backed by a single large donor.
    Settles each project's match through the rail."""
    pairs = quadratic_match(
        req.pool, [Project(p.wallet, list(p.contributions)) for p in req.projects]
    )
    projects: list[dict[str, Any]] = []
    total_settled = Decimal(0)
    for i, (p, match) in enumerate(pairs):
        tx_hash = _settle_to(f"qf:{i}", p.wallet, match, kind="qf")
        if tx_hash is not None:
            total_settled += match
        projects.append(
            {
                "wallet": p.wallet,
                "backers": len(p.contributions),
                "direct_total": str(sum(p.contributions, Decimal(0))),
                "match": str(match),
                "settled": tx_hash is not None,
                "tx_hash": tx_hash,
            }
        )
    return {"pool": str(req.pool), "projects": projects, "total_matched": str(total_settled)}


class RetroProject(BaseModel):
    wallet: str = Field(description="0x wallet of the project/creator")
    impact: int = Field(ge=0, description="Realized impact: distinct people who engaged")

    @field_validator("wallet")
    @classmethod
    def _check_wallet(cls, v: str) -> str:
        if not _HEX_WALLET.match(v):
            raise ValueError(f"invalid wallet: {v!r}")
        return v


class RetroRequest(BaseModel):
    pool: Decimal = Field(gt=0, description="Retroactive pool to distribute after the fact")
    projects: list[RetroProject] = Field(min_length=1)


@app.post("/retro", tags=["primitives"])
def retro(req: RetroRequest) -> dict[str, Any]:
    """Retroactive funding (PA 07): pay out a pool *after the fact* to what proved valuable,
    weighted quadratically by realized impact (distinct engagers) — breadth of impact wins,
    not who shouted loudest. Each engager counts as one unit, so weight = impact². Settles
    each project's award through the rail."""
    pairs = quadratic_match(
        req.pool, [Project(p.wallet, [Decimal(1)] * p.impact) for p in req.projects]
    )
    projects: list[dict[str, Any]] = []
    total_settled = Decimal(0)
    for i, ((p, award), src) in enumerate(zip(pairs, req.projects, strict=True)):
        tx_hash = _settle_to(f"retro:{i}", p.wallet, award, kind="retro")
        if tx_hash is not None:
            total_settled += award
        projects.append(
            {
                "wallet": p.wallet,
                "impact": src.impact,
                "award": str(award),
                "settled": tx_hash is not None,
                "tx_hash": tx_hash,
            }
        )
    return {"pool": str(req.pool), "projects": projects, "total_awarded": str(total_settled)}


class SendRequest(BaseModel):
    to: str = Field(description="0x recipient wallet")
    amount: Decimal = Field(gt=0, description="USDC to send")
    memo: str = Field(
        default="", max_length=280, description="Provenance memo travelling with the payment"
    )
    kind: str = Field(default="note", description="What the payment is for (recibo memo taxonomy)")
    ref: str = Field(
        default="", max_length=280, description="Referenced thing: citation URL, hash, job id"
    )
    confidential: bool = Field(
        default=False,
        description="Redact the memo note in the public feed (recibo encrypted scheme)",
    )
    refund_to: str = Field(
        default="",
        description="0x refund destination, bound at send time (circlefin/refund-protocol)",
    )

    @field_validator("to")
    @classmethod
    def _check_wallet(cls, v: str) -> str:
        if not _HEX_WALLET.match(v):
            raise ValueError(f"invalid wallet: {v!r}")
        return v

    @field_validator("refund_to")
    @classmethod
    def _check_refund_to(cls, v: str) -> str:
        if v and not _HEX_WALLET.match(v):
            raise ValueError(f"invalid refund_to: {v!r}")
        return v


@app.post("/send", tags=["primitives"])
def send(req: SendRequest) -> dict[str, Any]:
    """Send USDC with a provenance memo (Arc "Send USDC with a memo" / circlefin/recibo).

    A plain transfer whose memo carries why it was paid — a citation URL, an attestation hash,
    a job id. The memo is bound to the settlement and retrievable by tx via GET /memo/{tx}."""
    tx_hash = _settle_to(f"send:{len(_memos)}", req.to, req.amount, kind="send")
    memo = build_memo(
        kind=req.kind,
        ref=req.ref,
        note=req.memo,
        message_from=signer.address,
        message_to=req.to,
        confidential=req.confidential,
    )
    if tx_hash is not None:
        _record_memo(tx_hash, memo)
        _sends[tx_hash] = {
            "to": req.to,
            "amount": req.amount,
            "refund_to": req.refund_to,
            "refunded": False,
        }
    return {
        "to": req.to,
        "amount": str(req.amount),
        "memo": memo.line(),
        "kind": memo.kind,
        "ref": memo.ref,
        "settled": tx_hash is not None,
        "tx_hash": tx_hash,
    }


# Dispute reason codes (a small taxonomy over circlefin/refund-protocol's generic refund).
RefundReason = Literal["requested", "not_delivered", "duplicate", "fraud", "other"]


class RefundRequest(BaseModel):
    reason: RefundReason = Field(default="requested", description="Why the payment is disputed")
    by: Literal["recipient", "arbiter"] = Field(
        default="recipient", description="Who initiated the refund (refund-protocol roles)"
    )
    refund_to: str = Field(
        default="", description="Override refund destination (only if none was bound at send)"
    )

    @field_validator("refund_to")
    @classmethod
    def _check_refund_to(cls, v: str) -> str:
        if v and not _HEX_WALLET.match(v):
            raise ValueError(f"invalid refund_to: {v!r}")
        return v


@app.post("/refund/{tx_hash}", tags=["primitives"])
def refund(tx_hash: str, req: RefundRequest) -> dict[str, Any]:
    """Refund/dispute a send — settle the amount to the bound ``refund_to`` (ported from
    circlefin/refund-protocol: the refund destination is set at pay time, refundable by the
    recipient or an arbiter). Carries a dispute reason; idempotency-guarded (refunds once)."""
    record = _sends.get(tx_hash)
    if record is None:
        return {"found": False, "tx_hash": tx_hash}
    if record["refunded"]:
        return {"error": "already_refunded", "tx_hash": tx_hash}
    destination = record["refund_to"] or req.refund_to
    if not destination:
        return {"error": "no_refund_address", "tx_hash": tx_hash}
    refund_tx = _settle_to(f"refund:{tx_hash}", destination, record["amount"], kind="refund")
    if refund_tx is not None:
        record["refunded"] = True
        _record_memo(
            refund_tx,
            build_memo(
                kind="refund",
                ref=tx_hash,
                note=f"{req.reason}, by {req.by}",
                message_from=destination,
                message_to=destination,
            ),
        )
    return {
        "refunded": refund_tx is not None,
        "original_tx": tx_hash,
        "amount": str(record["amount"]),
        "refund_to": destination,
        "reason": req.reason,
        "by": req.by,
        "refund_tx": refund_tx,
    }


class SwapRequest(BaseModel):
    token_in: str = Field(default="USDC", description="Stablecoin to sell (USDC|EURC)")
    token_out: str = Field(default="EURC", description="Stablecoin to buy (USDC|EURC)")
    amount_in: Decimal = Field(gt=0, description="Amount of token_in to swap")
    to: str = Field(default="", description="0x wallet to receive token_out (optional)")

    @field_validator("to")
    @classmethod
    def _check_to(cls, v: str) -> str:
        if v and not _HEX_WALLET.match(v):
            raise ValueError(f"invalid wallet: {v!r}")
        return v


def _quote_payload(q: Any) -> dict[str, Any]:
    return {
        "token_in": q.token_in,
        "token_out": q.token_out,
        "amount_in": str(q.amount_in),
        "amount_out": str(q.amount_out),
        "app_fee_bps": q.app_fee_bps,
        "app_fee": str(q.app_fee),
        "effective_rate": str(q.effective_rate),
    }


@app.post("/swap/quote", tags=["primitives"])
def swap_quote_endpoint(req: SwapRequest) -> dict[str, Any]:
    """Quote a USDC<->EURC stablecoin swap (ported from circlefin/arc-stablecoin-fx
    estimateSwap): gross at the mock FX rate, less an app fee in bps. Offline — no funds."""
    try:
        q = swap_quote(req.token_in, req.token_out, req.amount_in, settings.swap_app_fee_bps)
    except SwapError as exc:
        return {"error": str(exc)}
    return _quote_payload(q)


@app.post("/swap", tags=["primitives"])
def swap(req: SwapRequest) -> dict[str, Any]:
    """Execute a stablecoin swap (offline App Kit kit.swap() analogue): quote, then settle the
    net token_out to the recipient through the active rail. The real on-chain path is
    rail/appkit swapOnArc (kit key + funds gated)."""
    try:
        q = swap_quote(req.token_in, req.token_out, req.amount_in, settings.swap_app_fee_bps)
    except SwapError as exc:
        return {"error": str(exc)}
    destination = req.to or _demo_wallet(7)
    tx_hash = _settle_to(f"swap:{q.token_in}-{q.token_out}", destination, q.amount_out, kind="swap")
    if tx_hash is not None:
        _record_memo(
            tx_hash,
            build_memo(
                kind="swap",
                ref=f"{q.token_in}->{q.token_out}",
                note=f"{q.amount_in} {q.token_in} -> {q.amount_out} {q.token_out}",
                message_from=signer.address,
                message_to=destination,
            ),
        )
    payload = _quote_payload(q)
    payload.update({"to": destination, "settled": tx_hash is not None, "tx_hash": tx_hash})
    return payload


# --- Approved-action settlement workflows (circle-ooak intent/approve/execute) ---


class SettlementIntent(BaseModel):
    to: str = Field(description="0x recipient wallet")
    amount: Decimal = Field(gt=0, description="USDC to settle")
    kind: str = Field(default="workflow", description="Traction kind for this settlement")

    @field_validator("to")
    @classmethod
    def _check_wallet(cls, v: str) -> str:
        if not _HEX_WALLET.match(v):
            raise ValueError(f"invalid wallet: {v!r}")
        return v

    def args(self) -> dict[str, object]:
        # Canonical args for intent matching (amount as string so JSON is stable).
        return {"to": self.to, "amount": str(self.amount), "kind": self.kind}


class ApproveRequest(BaseModel):
    intents: list[SettlementIntent] = Field(min_length=1, description="Batch to approve together")


@app.post("/workflow/intent", tags=["primitives"])
def workflow_intent(req: SettlementIntent) -> dict[str, Any]:
    """Phase 1 (circle-ooak): describe a settlement without running it — returns its intent."""
    return _workflows.create_intent("settle", req.args())


@app.post("/workflow/approve", tags=["primitives"])
def workflow_approve(req: ApproveRequest) -> dict[str, Any]:
    """Phase 2: approve a batch of settlement intents together; returns a workflow id."""
    intents: list[dict[str, object]] = [
        {"function": "settle", "args": i.args()} for i in req.intents
    ]
    try:
        wfid = _workflows.approve(intents)
    except WorkflowError as exc:
        return {"error": str(exc)}
    return {"wfid": wfid, "approved": len(intents)}


@app.post("/workflow/{wfid}/execute", tags=["primitives"])
def workflow_execute(wfid: str, req: SettlementIntent) -> dict[str, Any]:
    """Phase 3: execute one approved settlement — it must match the approved next action, in
    order. Settles via the rail only after the guard passes (nothing unapproved settles)."""
    try:
        action = _workflows.check(wfid, "settle", req.args())
    except WorkflowError as exc:
        return {"error": str(exc), "wfid": wfid}
    tx_hash = _settle_to(f"workflow:{wfid}", req.to, req.amount, kind=req.kind)
    _workflows.complete(wfid, action, tx_hash or "", ok=tx_hash is not None)
    return {
        "wfid": wfid,
        "settled": tx_hash is not None,
        "tx_hash": tx_hash,
        "to": req.to,
        "amount": str(req.amount),
    }


@app.get("/workflow/{wfid}", tags=["primitives"])
def workflow_status(wfid: str) -> dict[str, Any]:
    """Read a workflow's status and per-action progress (audit the approved settlement batch)."""
    wf = _workflows.get(wfid)
    if wf is None:
        return {"found": False, "wfid": wfid}
    return {
        "found": True,
        "wfid": wfid,
        "status": wf.status.value,
        "cursor": wf.cursor,
        "remaining": wf.remaining(),
        "actions": [
            {"intent": a.intent, "status": a.status.value, "result": a.result} for a in wf.actions
        ],
    }


# --- Split-bill money requests (arc-p2p-payments "request money") ---


class RequestCreate(BaseModel):
    payee: str = Field(description="0x wallet that receives the collected funds")
    payers: list[str] = Field(min_length=1, description="0x wallets that split the total")
    total: Decimal = Field(gt=0, description="USDC total to split equally across payers")

    @field_validator("payee")
    @classmethod
    def _check_payee(cls, v: str) -> str:
        if not _HEX_WALLET.match(v):
            raise ValueError(f"invalid payee: {v!r}")
        return v

    @field_validator("payers")
    @classmethod
    def _check_payers(cls, v: list[str]) -> list[str]:
        for p in v:
            if not _HEX_WALLET.match(p):
                raise ValueError(f"invalid payer: {p!r}")
        return v


def _request_view(req: Any) -> dict[str, Any]:
    return {
        "id": req.id,
        "payee": req.payee,
        "total": str(req.total),
        "status": req.status.value,
        "collected": str(req.collected()),
        "outstanding": str(req.outstanding()),
        "shares": [
            {"payer": s.payer, "amount": str(s.amount), "paid": s.paid, "tx_hash": s.tx_hash}
            for s in req.shares
        ],
    }


@app.post("/request", tags=["primitives"])
def create_request(req: RequestCreate) -> dict[str, Any]:
    """Open a split-bill money request — a payee asks payers to cover a total, split dust-free
    (ported from circlefin/arc-p2p-payments "request money"). Payers fulfil per share."""
    try:
        r = _requests.create(req.payee, req.payers, req.total)
    except RequestError as exc:
        return {"error": str(exc)}
    return _request_view(r)


class FulfilRequest(BaseModel):
    payer: str = Field(description="0x wallet of the payer settling their share")

    @field_validator("payer")
    @classmethod
    def _check_payer(cls, v: str) -> str:
        if not _HEX_WALLET.match(v):
            raise ValueError(f"invalid payer: {v!r}")
        return v


@app.post("/request/{rid}/fulfil", tags=["primitives"])
def fulfil_request(rid: str, body: FulfilRequest) -> dict[str, Any]:
    """Fulfil one payer's share — settles their portion to the request's payee via the rail,
    then marks the share paid (two-step so a failed settlement never marks it paid)."""
    req = _requests.get(rid)
    if req is None:
        return {"found": False, "id": rid}
    try:
        share = _requests.fulfil(rid, body.payer)
    except RequestError as exc:
        return {"error": str(exc), "id": rid}
    tx_hash = _settle_to(f"request:{rid}:{body.payer}", req.payee, share.amount, kind="request")
    if tx_hash is None:
        return {"error": "settlement_failed", "id": rid}
    _requests.settled(share, tx_hash)
    _record_memo(
        tx_hash,
        build_memo(
            kind="invoice",
            ref=rid,
            note=f"share of {req.total} to {req.payee}",
            message_from=body.payer,
            message_to=req.payee,
        ),
    )
    return {"id": rid, "settled": True, "tx_hash": tx_hash, **_request_view(req)}


@app.get("/request/{rid}", tags=["primitives"])
def get_request(rid: str) -> dict[str, Any]:
    """Read a money request's status — collected vs outstanding, per-payer share progress."""
    req = _requests.get(rid)
    if req is None:
        return {"found": False, "id": rid}
    return {"found": True, **_request_view(req)}


# --- Prepaid credits (arc-commerce buy-credits-with-USDC) ---

# Treasury that receives prepaid top-ups (a real deployment uses a Circle wallet; here a
# deterministic demo address so the settlement is visible end to end). The Treasury ledger
# tracks its accumulated balance and supports a sweep (arc-fintech rebalance).
_CREDIT_TREASURY = _demo_wallet(0)
_treasury = Treasury(wallet=_CREDIT_TREASURY)


class TopupRequest(BaseModel):
    wallet: str = Field(description="0x wallet topping up its credit balance")
    amount: Decimal = Field(gt=0, description="USDC to prepay into credits")

    @field_validator("wallet")
    @classmethod
    def _check_wallet(cls, v: str) -> str:
        if not _HEX_WALLET.match(v):
            raise ValueError(f"invalid wallet: {v!r}")
        return v


class SpendRequest(BaseModel):
    wallet: str = Field(description="0x wallet spending prepaid credits")
    amount: Decimal = Field(gt=0, description="Credits to draw down")
    reason: str = Field(default="citation", max_length=120, description="What the credits buy")

    @field_validator("wallet")
    @classmethod
    def _check_wallet(cls, v: str) -> str:
        if not _HEX_WALLET.match(v):
            raise ValueError(f"invalid wallet: {v!r}")
        return v


def _credit_view(acct: Any) -> dict[str, Any]:
    return {
        "wallet": acct.wallet,
        "balance": str(acct.balance),
        "entries": [
            {
                "kind": e.kind.value,
                "amount": str(e.amount),
                "reason": e.reason,
                "tx_hash": e.tx_hash,
            }
            for e in acct.entries
        ],
    }


@app.post("/credits/topup", tags=["primitives"])
def credits_topup(req: TopupRequest) -> dict[str, Any]:
    """Prepay USDC into a credit balance (ported from circlefin/arc-commerce): settles the
    amount to the treasury, then credits the wallet. One settlement funds many later spends."""
    tx_hash = _settle_to(f"credits:{req.wallet}", _CREDIT_TREASURY, req.amount, kind="topup")
    if tx_hash is None:
        return {"error": "settlement_failed", "wallet": req.wallet}
    acct = _credits.credit(req.wallet, req.amount, tx_hash)
    _treasury.deposit(req.amount, req.wallet, tx_hash)
    _record_memo(
        tx_hash,
        build_memo(
            kind="invoice",
            ref="credits-topup",
            note=f"prepaid {req.amount} USDC",
            message_from=req.wallet,
            message_to=_CREDIT_TREASURY,
        ),
    )
    return {"topped_up": True, "tx_hash": tx_hash, **_credit_view(acct)}


@app.post("/credits/spend", tags=["primitives"])
def credits_spend(req: SpendRequest) -> dict[str, Any]:
    """Draw down prepaid credits for an action (no on-chain move — already paid at top-up).
    Returns ``insufficient_credits`` if the balance is too low."""
    try:
        acct = _credits.spend(req.wallet, req.amount, req.reason)
    except CreditError as exc:
        return {"error": str(exc), "wallet": req.wallet}
    return {"spent": True, "reason": req.reason, **_credit_view(acct)}


@app.get("/credits/{wallet}", tags=["primitives"])
def credits_balance(wallet: str) -> dict[str, Any]:
    """Read a wallet's prepaid credit balance and its top-up/spend history."""
    acct = _credits.get(wallet)
    if acct is None:
        return {"found": False, "wallet": wallet, "balance": "0"}
    return {"found": True, **_credit_view(acct)}


# --- Gateway unified balance (arc-multichain-wallet cross-chain deposit) ---

# Gateway contract that receives cross-chain deposits (deterministic demo address offline).
_GATEWAY_WALLET = _demo_wallet(1)


class GatewayDeposit(BaseModel):
    wallet: str = Field(description="0x wallet whose unified balance is credited")
    chain: str = Field(
        default="arcTestnet", description=f"Source chain ({', '.join(SUPPORTED_CHAINS)})"
    )
    amount: Decimal = Field(gt=0, description="USDC to deposit from the source chain")

    @field_validator("wallet")
    @classmethod
    def _check_wallet(cls, v: str) -> str:
        if not _HEX_WALLET.match(v):
            raise ValueError(f"invalid wallet: {v!r}")
        return v


def _gateway_view(acct: Any) -> dict[str, Any]:
    return {
        "wallet": acct.wallet,
        "balance": str(acct.balance),
        "by_chain": {c: str(a) for c, a in acct.by_chain.items()},
        "deposits": [
            {"chain": d.chain, "amount": str(d.amount), "tx_hash": d.tx_hash} for d in acct.deposits
        ],
    }


@app.get("/gateway/chains", tags=["primitives"])
def gateway_chains() -> dict[str, Any]:
    """The source chains a Gateway deposit can originate from (arc-multichain-wallet)."""
    return {"chains": list(SUPPORTED_CHAINS)}


@app.post("/gateway/deposit", tags=["primitives"])
def gateway_deposit(req: GatewayDeposit) -> dict[str, Any]:
    """Deposit USDC from a source chain into the wallet's unified Gateway balance (ported from
    circlefin/arc-multichain-wallet). The cross-chain move is mocked; settles to the gateway."""
    try:
        chain = normalize_chain(req.chain)
    except GatewayError as exc:
        return {"error": str(exc), "wallet": req.wallet}
    tx_hash = _settle_to(
        f"gateway:{req.wallet}:{chain}", _GATEWAY_WALLET, req.amount, kind="deposit"
    )
    if tx_hash is None:
        return {"error": "settlement_failed", "wallet": req.wallet}
    acct = _gateway.deposit(req.wallet, chain, req.amount, tx_hash)
    return {"deposited": True, "chain": chain, "tx_hash": tx_hash, **_gateway_view(acct)}


@app.get("/gateway/{wallet}", tags=["primitives"])
def gateway_balance(wallet: str) -> dict[str, Any]:
    """Read a wallet's unified Gateway balance and its per-chain deposit breakdown."""
    acct = _gateway.get(wallet)
    if acct is None:
        return {"found": False, "wallet": wallet, "balance": "0"}
    return {"found": True, **_gateway_view(acct)}


@app.get("/balance", tags=["ledger-ops"])
def balance() -> dict[str, Any]:
    """Unified balance — one aggregated view of the agent's economic state across every book
    (ported from circlefin/arc-multichain-wallet's unified-balance UX). Rolls up settled
    volume, prepaid credits outstanding, and open split-bill requests into a single summary."""
    return {
        "settled": traction.summary(),
        "credits": _credits.summary(),
        "requests": _requests.summary(),
        "treasury": _treasury_view(),
        "gateway": _gateway.summary(),
    }


# --- Treasury sweep (arc-fintech multi-chain treasury / rebalance) ---


def _treasury_view() -> dict[str, Any]:
    return {
        "wallet": _treasury.wallet,
        "balance": str(_treasury.balance),
        "sweepable": _treasury.sweepable(settings.treasury_sweep_threshold),
        "threshold": str(settings.treasury_sweep_threshold),
        "flows": [
            {
                "kind": f.kind.value,
                "amount": str(f.amount),
                "counterparty": f.counterparty,
                "tx_hash": f.tx_hash,
            }
            for f in _treasury.flows
        ],
    }


class SweepRequest(BaseModel):
    to: str = Field(description="0x destination wallet to sweep the treasury balance to")

    @field_validator("to")
    @classmethod
    def _check_to(cls, v: str) -> str:
        if not _HEX_WALLET.match(v):
            raise ValueError(f"invalid wallet: {v!r}")
        return v


@app.get("/treasury", tags=["ledger-ops"])
def treasury_status() -> dict[str, Any]:
    """Read the agent's treasury — accumulated prepaid-credit inflows, sweep flows, and whether
    the balance has crossed the sweep threshold (ported from circlefin/arc-fintech)."""
    return _treasury_view()


@app.post("/treasury/sweep", tags=["ledger-ops"])
def treasury_sweep(req: SweepRequest) -> dict[str, Any]:
    """Sweep the whole treasury balance to a destination (arc-fintech rebalance): settles the
    balance via the rail, then zeroes the treasury. Errors if there's nothing to sweep."""
    try:
        amount = _treasury.prepare_sweep()
    except TreasuryError as exc:
        return {"error": str(exc)}
    tx_hash = _settle_to(f"treasury-sweep:{req.to}", req.to, amount, kind="sweep")
    if tx_hash is None:
        return {"error": "settlement_failed"}
    _treasury.swept(amount, req.to, tx_hash)
    return {
        "swept": True,
        "amount": str(amount),
        "to": req.to,
        "tx_hash": tx_hash,
        **_treasury_view(),
    }


def _memo_item(tx_hash: str, *, public: bool) -> dict[str, Any]:
    """A receipt: the tx, its one-line memo, and the structured recibo envelope (if any).

    ``public=True`` (the /memos feed) redacts a confidential note; a direct read returns it.
    """
    memo = _memo_objs.get(tx_hash)
    meta = memo.as_dict(public=public) if memo is not None else None
    return {"tx_hash": tx_hash, "memo": _memos.get(tx_hash), "meta": meta}


@app.get("/memo/{tx_hash}", tags=["ledger-ops"])
def get_memo(tx_hash: str) -> dict[str, Any]:
    """Read the provenance memo bound to a settlement tx (recibo-style receipt) — full note,
    even when confidential (a direct read stands in for a counterparty decrypting it)."""
    found = tx_hash in _memos or tx_hash in _memo_objs
    return {"found": found, **_memo_item(tx_hash, public=False)}


@app.get("/memos", tags=["ledger-ops"])
def list_memos(limit: int = 20, kind: str = "") -> dict[str, Any]:
    """Recent provenance memos (most recent first) — a recibo-style feed of why payments were
    made. Confidential notes are redacted here. Optional ``kind`` filters the feed."""
    # _memo_objs preserves insertion order and every recorded memo has an envelope.
    items = [_memo_item(tx, public=True) for tx in reversed(list(_memo_objs))]
    if kind:
        k = kind.strip().lower()
        items = [it for it in items if (it["meta"] or {}).get("kind") == k]
    return {"count": len(items), "memos": items[: max(0, limit)]}


@app.get("/traction", tags=["ledger-ops"])
def get_traction() -> dict[str, Any]:
    """Settled volume rolled up across every primitive — the traction story in one call."""
    return traction.summary()


class DemoRequest(BaseModel):
    rounds: int = Field(default=3, ge=1, le=50, description="Rounds of every primitive to run")


_demo_offset = 0


@app.post("/demo/run", tags=["ledger-ops"])
def demo_run(req: DemoRequest) -> dict[str, Any]:
    """Generate sample volume server-side: run ``rounds`` of every primitive and return the
    rolled-up traction. One call for the dashboard's 'generate volume' button (agents are the
    users) — settles through the active rail like every other endpoint."""
    global _demo_offset
    start = _demo_offset
    _demo_offset += req.rounds * 20 + 20  # distinct wallets across runs
    for r in range(req.rounds):
        _sample_round(start + r * 20)
    return {"rounds": req.rounds, "traction": traction.summary()}


@app.post("/demo/reset", tags=["ledger-ops"])
def demo_reset() -> dict[str, Any]:
    """Clear in-memory demo state (traction, bonds, streams, memos) for a clean walkthrough.

    Does NOT touch the citation ledger or any chain state — only the primitive sandboxes."""
    global traction, bonds, streams, _demo_offset
    global _credits, _requests, _workflows, _treasury, _gateway
    traction = TractionBook()
    bonds = BondBook()
    streams = StreamBook()
    _credits = CreditBook()
    _requests = RequestBook()
    _workflows = WorkflowManager()
    _treasury = Treasury(wallet=_CREDIT_TREASURY)
    _gateway = GatewayBook()
    _memos.clear()
    _memo_objs.clear()
    _sends.clear()
    _demo_offset = 0
    return {"reset": True, "traction": traction.summary()}


@app.get("/status", tags=["ledger-ops"])
def status() -> dict[str, Any]:
    """One-call dashboard bootstrap: live config + traction + citation metrics + which
    capabilities are enabled. Lets the UI render the whole picture from a single fetch."""
    return {
        "rail": type(rail).__name__,
        "grounding_threshold": settings.grounding_threshold,
        "sources_indexed": len(registry.all()),
        "llm_enabled": llm_enabled(settings),
        **_embedder_status(),
        "capabilities": {
            "erc8004": _erc8004 is not None,
            "erc8183": _erc8183 is not None,
            "circle_wallets": _circle is not None,
            "chain_verified_ledger": _chain_reader is not None,
        },
        "traction": traction.summary(),
        "citation_metrics": ledger.metrics(),
        "books": _books_summary(),
    }


def _books_summary() -> dict[str, Any]:
    """Live counts across the in-memory primitive books — the agent's economic surface area."""
    return {
        "credits": _credits.summary(),
        "requests": _requests.summary(),
        "treasury": {
            **_treasury.summary(),
            "sweepable": _treasury.sweepable(settings.treasury_sweep_threshold),
        },
        "workflows": _workflows.summary(),
        "gateway": _gateway.summary(),
        "memos": len(_memo_objs),
        "sends": len(_sends),
    }


@app.post("/attestation/verify", tags=["research"])
def attestation_verify(att: Attestation) -> dict[str, Any]:
    """Verify a signed attestation independently — "don't trust us, check the signature".

    Recomputes the signature over the canonical payload against ``agent_pubkey``. Lets anyone
    audit a citation attestation (e.g. pasted from an /ask response) without trusting Keryx.
    """
    return {
        "verified": verify_attestation(att),
        "agent_pubkey": att.agent_pubkey,
        "query_hash": att.query_hash,
        "citations": len(att.citations),
    }


@app.get("/metrics", tags=["ledger-ops"])
def metrics() -> dict[str, Any]:
    """Traction metrics — the numbers we lead with (prd.md §8)."""
    return ledger.metrics()


@app.get("/ledger", tags=["ledger-ops"])
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


@app.get("/reconcile", tags=["ledger-ops"])
def reconcile(limit: int = 50) -> dict[str, Any]:
    """Reconcile the off-chain ledger against chain — "don't trust our DB, here's the chain".

    Confirms each recent citation tx on Arc and reports matched vs unverified counts and the
    on-chain-reconciled total. Opt-in (KERYX_LEDGER_VERIFY_CHAIN); without it the ledger is
    the mirror and there is nothing to reconcile against.
    """
    recent = ledger.recent(limit)
    if _chain_reader is None:
        return {"enabled": False, "ledger_rows": len(recent)}
    annotated = annotate_recent(_chain_reader, recent)
    entries_obj = annotated["entries"]
    entries: list[Any] = entries_obj if isinstance(entries_obj, list) else []
    unverified = [
        {"tx_hash": e.get("tx_hash"), "reason": e.get("chain_reason")}
        for e in entries
        if not e.get("chain_verified")
    ]
    return {
        "enabled": True,
        "ledger_rows": len(entries),
        "verified": annotated["verified_count"],
        "unverified": len(unverified),
        "reconciled_usdc": annotated["reconciled_usdc"],
        "mismatches": unverified[:limit],
        "in_sync": len(unverified) == 0,
    }
