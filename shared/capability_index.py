"""Capability index — a machine-readable map of every primitive and its provenance.

Each entry names a capability, its HTTP endpoints, the category, and (where it's a port of a
Circle open-source repo) the upstream under ``vendor/circle/``. Powers GET /capabilities so the
dashboard and reviewers get one source of truth for what the agent does and where it came from.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    name: str
    category: str  # "split" | "credit" | "settlement" | "provenance" | "treasury" | "onchain"
    endpoints: tuple[str, ...]
    summary: str
    upstream: str | None = None  # circlefin repo this is ported from, if any

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "category": self.category,
            "endpoints": list(self.endpoints),
            "summary": self.summary,
            "upstream": self.upstream,
            "ported": self.upstream is not None,
        }


# Curated catalog. Original Keryx primitives have no upstream; ports name their Circle repo.
CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        "Royalty split",
        "split",
        ("POST /payout",),
        "Pay every credited contributor in proportion (dust-free).",
    ),
    Capability(
        "User royalties",
        "split",
        ("POST /royalties",),
        "A listener budget pays only who they played, play-gated.",
    ),
    Capability(
        "Quadratic funding",
        "split",
        ("POST /qf",),
        "Match a pool by breadth — (Σ√contribution)².",
    ),
    Capability(
        "Retroactive funding",
        "split",
        ("POST /retro",),
        "Award a pool after the fact by realized impact².",
    ),
    Capability(
        "Reputation bond",
        "settlement",
        ("POST /bond", "POST /bond/{id}/resolve"),
        "Collateral that slashes to the claimant on default; optional ERC-8183 escrow anchor.",
    ),
    Capability(
        "Streaming",
        "settlement",
        ("POST /stream", "POST /stream/{id}/tick"),
        "Pay-per-second flow billed live with no dust.",
    ),
    Capability(
        "Send with memo",
        "provenance",
        ("POST /send", "GET /memo/{tx}"),
        "A transfer whose structured memo carries why it was paid.",
        upstream="recibo",
    ),
    Capability(
        "Confidential + threaded memos",
        "provenance",
        ("GET /memos", "GET /memo/{tx}/thread"),
        "Redacted-in-feed notes and reply threads over the memo envelope.",
        upstream="recibo",
    ),
    Capability(
        "Stablecoin swap",
        "settlement",
        ("POST /swap/quote", "POST /swap"),
        "USDC↔EURC at the mock FX rate less an app fee in bps.",
        upstream="arc-stablecoin-fx",
    ),
    Capability(
        "Split-bill request",
        "settlement",
        ("POST /request", "POST /request/{id}/fulfil"),
        "A payee splits a total across payers; each fulfils their share.",
        upstream="arc-p2p-payments",
    ),
    Capability(
        "Prepaid credits + tiers",
        "credit",
        ("POST /credits/topup", "POST /credits/spend", "GET /credits/tiers"),
        "Top up USDC once, draw down per action; tiers give bonus credits.",
        upstream="arc-commerce",
    ),
    Capability(
        "Approved-action workflow",
        "settlement",
        ("POST /workflow/approve", "POST /workflow/{id}/execute"),
        "Approve a settlement batch, execute in order — nothing unapproved settles.",
        upstream="circle-ooak",
    ),
    Capability(
        "Refund / dispute",
        "settlement",
        ("POST /refund/{tx}",),
        "Refund to the address bound at send, with a dispute reason.",
        upstream="refund-protocol",
    ),
    Capability(
        "Treasury + sweep",
        "treasury",
        ("GET /treasury", "POST /treasury/sweep"),
        "Accumulate prepaid inflows; sweep to a destination over threshold.",
        upstream="arc-fintech",
    ),
    Capability(
        "Gateway unified balance",
        "treasury",
        ("POST /gateway/deposit", "POST /gateway/spend", "GET /gateway/{wallet}"),
        "Deposit USDC from many chains into one Arc-spendable balance.",
        upstream="arc-multichain-wallet",
    ),
    Capability(
        "ERC-8183 job escrow",
        "onchain",
        ("GET /job/{id}",),
        "Read an on-chain AgenticCommerce job's escrow state (opt-in).",
        upstream="arc-escrow",
    ),
    Capability(
        "Unified balance summary",
        "treasury",
        ("GET /balance",),
        "One aggregated view of settled volume + credits + treasury + gateway.",
    ),
)


def index() -> dict[str, object]:
    """The full catalog plus rollup counts (total, ported, by category)."""
    by_category: dict[str, int] = {}
    for c in CAPABILITIES:
        by_category[c.category] = by_category.get(c.category, 0) + 1
    return {
        "count": len(CAPABILITIES),
        "ported": sum(1 for c in CAPABILITIES if c.upstream is not None),
        "by_category": by_category,
        "capabilities": [c.as_dict() for c in CAPABILITIES],
    }
