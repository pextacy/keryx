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
    example: str = ""  # a one-line example call (curl) so the row is copy-paste runnable

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "category": self.category,
            "endpoints": list(self.endpoints),
            "summary": self.summary,
            "upstream": self.upstream,
            "ported": self.upstream is not None,
            "example": self.example,
        }


# Curated catalog. Original Keryx primitives have no upstream; ports name their Circle repo.
CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        "Royalty split",
        "split",
        ("POST /payout",),
        "Pay every credited contributor in proportion (dust-free).",
        example='curl -s localhost:8000/payout -d \'{"amount":"0.01","contributors":[{"wallet":"0xa..a","share":"60"},{"wallet":"0xb..b","share":"40"}]}\' -H content-type:application/json',
    ),
    Capability(
        "User royalties",
        "split",
        ("POST /royalties",),
        "A listener budget pays only who they played, play-gated.",
        example='curl -s localhost:8000/royalties -d \'{"budget":"0.01","plays":[{"wallet":"0xa..a","count":30}],"min_count":1}\' -H content-type:application/json',
    ),
    Capability(
        "Quadratic funding",
        "split",
        ("POST /qf",),
        "Match a pool by breadth — (Σ√contribution)².",
        example='curl -s localhost:8000/qf -d \'{"pool":"0.01","projects":[{"wallet":"0xa..a","contributions":["1","1","1"]}]}\' -H content-type:application/json',
    ),
    Capability(
        "Retroactive funding",
        "split",
        ("POST /retro",),
        "Award a pool after the fact by realized impact².",
        example='curl -s localhost:8000/retro -d \'{"pool":"0.01","projects":[{"wallet":"0xa..a","impact":40}]}\' -H content-type:application/json',
    ),
    Capability(
        "Reputation bond",
        "settlement",
        ("POST /bond", "POST /bond/{id}/resolve"),
        "Collateral that slashes to the claimant on default; optional ERC-8183 escrow anchor.",
        example='curl -s localhost:8000/bond -d \'{"provider":"0x1..1","claimant":"0x2..2","amount":"0.01"}\' -H content-type:application/json',
    ),
    Capability(
        "Streaming",
        "settlement",
        ("POST /stream", "POST /stream/{id}/tick"),
        "Pay-per-second flow billed live with no dust.",
        example='curl -s localhost:8000/stream -d \'{"payer":"0x1..1","payee":"0x2..2","rate":"0.001"}\' -H content-type:application/json',
    ),
    Capability(
        "Recurring schedule",
        "settlement",
        ("POST /schedule", "POST /schedule/{id}/run"),
        "A fixed amount paid per run for N runs — subscription/payroll style.",
        upstream="arc-fintech",
        example='curl -s localhost:8000/schedule -d \'{"payer":"0xa..a","payee":"0xb..b","amount":"0.002","runs":3}\' -H content-type:application/json',
    ),
    Capability(
        "Send with memo",
        "provenance",
        ("POST /send", "GET /memo/{tx}"),
        "A transfer whose structured memo carries why it was paid.",
        upstream="recibo",
        example='curl -s localhost:8000/send -d \'{"to":"0xa..a","amount":"0.01","kind":"citation","memo":"g=0.91"}\' -H content-type:application/json',
    ),
    Capability(
        "Confidential + threaded memos",
        "provenance",
        ("GET /memos", "GET /memo/{tx}/thread"),
        "Redacted-in-feed notes and reply threads over the memo envelope.",
        upstream="recibo",
        example="curl -s 'localhost:8000/memos?kind=citation&limit=10'",
    ),
    Capability(
        "Stablecoin swap",
        "settlement",
        ("POST /swap/quote", "POST /swap"),
        "USDC↔EURC at the mock FX rate less an app fee in bps.",
        upstream="arc-stablecoin-fx",
        example='curl -s localhost:8000/swap/quote -d \'{"token_in":"USDC","token_out":"EURC","amount_in":"10"}\' -H content-type:application/json',
    ),
    Capability(
        "Split-bill request",
        "settlement",
        ("POST /request", "POST /request/{id}/fulfil"),
        "A payee splits a total across payers; each fulfils their share.",
        upstream="arc-p2p-payments",
        example='curl -s localhost:8000/request -d \'{"payee":"0xe..e","payers":["0xa..a","0xb..b"],"total":"0.10"}\' -H content-type:application/json',
    ),
    Capability(
        "Prepaid credits + tiers",
        "credit",
        ("POST /credits/topup", "POST /credits/spend", "GET /credits/tiers"),
        "Top up USDC once, draw down per action; tiers give bonus credits.",
        upstream="arc-commerce",
        example='curl -s localhost:8000/credits/topup -d \'{"wallet":"0xa..a","tier":"pro"}\' -H content-type:application/json',
    ),
    Capability(
        "Multi-item order checkout",
        "settlement",
        ("POST /order", "POST /order/{id}/checkout"),
        "Bundle line-items paying different recipients into one order, settled at checkout.",
        upstream="arc-commerce",
        example='curl -s localhost:8000/order -d \'{"items":[{"description":"author","to":"0xa..a","amount":"0.003"}]}\' -H content-type:application/json',
    ),
    Capability(
        "Approved-action workflow",
        "settlement",
        ("POST /workflow/approve", "POST /workflow/{id}/execute"),
        "Approve a settlement batch, execute in order — nothing unapproved settles.",
        upstream="circle-ooak",
        example='curl -s localhost:8000/workflow/approve -d \'{"intents":[{"to":"0xa..a","amount":"0.01"}]}\' -H content-type:application/json',
    ),
    Capability(
        "Refund / dispute",
        "settlement",
        ("POST /refund/{tx}",),
        "Refund to the address bound at send, with a dispute reason.",
        upstream="refund-protocol",
        example='curl -s localhost:8000/refund/0x<tx> -d \'{"reason":"not_delivered"}\' -H content-type:application/json',
    ),
    Capability(
        "Treasury + sweep",
        "treasury",
        ("GET /treasury", "POST /treasury/sweep"),
        "Accumulate prepaid inflows; sweep to a destination over threshold.",
        upstream="arc-fintech",
        example="curl -s localhost:8000/treasury",
    ),
    Capability(
        "Gateway unified balance",
        "treasury",
        ("POST /gateway/deposit", "POST /gateway/spend", "GET /gateway/{wallet}"),
        "Deposit USDC from many chains into one Arc-spendable balance.",
        upstream="arc-multichain-wallet",
        example='curl -s localhost:8000/gateway/deposit -d \'{"wallet":"0xa..a","chain":"avalancheFuji","amount":"0.5"}\' -H content-type:application/json',
    ),
    Capability(
        "Milestone escrow",
        "settlement",
        ("POST /escrow", "POST /escrow/{id}/release"),
        "Lock a total across tranches; release each to the provider on approval.",
        upstream="arc-escrow",
        example='curl -s localhost:8000/escrow -d \'{"client":"0xa..a","provider":"0xb..b","milestones":[{"label":"draft","amount":"0.01"}]}\' -H content-type:application/json',
    ),
    Capability(
        "ERC-8183 job escrow",
        "onchain",
        ("GET /job/{id}",),
        "Read an on-chain AgenticCommerce job's escrow state (opt-in).",
        upstream="arc-escrow",
        example="curl -s localhost:8000/job/1",
    ),
    Capability(
        "Unified balance summary",
        "treasury",
        ("GET /balance",),
        "One aggregated view of settled volume + credits + treasury + gateway.",
        example="curl -s localhost:8000/balance",
    ),
    Capability(
        "Agent tools manifest",
        "onchain",
        ("GET /agent/tools", "GET /capabilities"),
        "Keryx's primitives as tool-use schemas an LLM agent can discover and invoke.",
        upstream="agent-stack-starter-kits",
        example="curl -s localhost:8000/agent/tools | jq '.tools[].name'",
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
