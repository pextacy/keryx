"""Curated offline source set — lets /ask run end-to-end with zero infra.

A small, real-topic corpus with author wallets so grounding has signal and the
"evaluated-but-not-cited" gate is visibly exercised (the off-topic source should
score below T). Replaced by live RSSHub ingest when wired.
"""

from __future__ import annotations

from registry.models import Source
from registry.store import InMemoryRegistry

_W1 = "0x" + "11" * 20
_W2 = "0x" + "22" * 20
_W3 = "0x" + "33" * 20

_SOURCES = [
    Source(
        source_id="src_arc_overview",
        url="https://example.com/arc-overview",
        title="Arc: a stablecoin-native L1",
        text=(
            "Arc is a stablecoin-native layer-1 blockchain where gas is paid in USDC "
            "rather than a separate native token. It is designed for low-latency, "
            "sub-cent payments between agents and services."
        ),
        author="alice",
        author_wallet=_W1,
    ),
    Source(
        source_id="src_nanopayments",
        url="https://example.com/nanopayments",
        title="Gateway nanopayments",
        text=(
            "Circle Gateway batches many small USDC authorizations and settles them on "
            "Arc in bulk, gasless and sub-second. This removes the per-payment fee floor "
            "so a single citation toll of a fraction of a cent can finally clear on chain."
        ),
        author="bob",
        author_wallet=_W2,
    ),
    Source(
        source_id="src_x402",
        url="https://example.com/x402",
        title="x402 payment flow",
        text=(
            "With x402 a seller returns HTTP 402 with payment requirements; the buyer "
            "retries with a signed EIP-3009 authorization which the seller verifies and "
            "settles. It turns any HTTP endpoint into a paid resource for agents."
        ),
        author="carol",
        author_wallet=_W3,
    ),
    Source(
        source_id="src_offtopic",
        url="https://example.com/gardening",
        title="A guide to growing tomatoes",
        text=(
            "Tomatoes need full sun, regular watering, and well-drained soil. Prune the "
            "suckers and stake the plants as they grow through the summer season."
        ),
        author="dave",
        author_wallet="0x" + "44" * 20,
    ),
]


def seeded_registry() -> InMemoryRegistry:
    reg = InMemoryRegistry()
    reg.add_many(_SOURCES)
    for s in _SOURCES:
        if s.author_wallet:
            reg.register_author(s.author, s.author_wallet)
    return reg
