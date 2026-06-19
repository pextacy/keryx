"""HttpRail — the real-rail bridge client. Mocks the payer HTTP so it runs in CI.

Proves HttpRail satisfies the same frozen Rail contract as MockRail (order preserved,
one Receipt per intent, failures mapped) without needing a live rail or funds.
"""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from agent.attestation import AttestationSigner
from agent.pipeline import AskPipeline, Session
from registry import seeded_registry
from shared.rail import HttpRail, Rail
from shared.types import CitationIntent, SettlementStatus

AUTHOR = "0x" + "ab" * 20


def _mock_transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_http_rail_is_a_rail() -> None:
    assert isinstance(HttpRail(), Rail)


def test_http_rail_maps_receipts_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    intents = [
        CitationIntent(source_id="s1", author_wallet=AUTHOR, amount=Decimal("0.001")),
        CitationIntent(source_id="s2", author_wallet=AUTHOR, amount=Decimal("0.002")),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        assert "s1" in body and "s2" in body
        # Return out of order + one failure to prove ordering + status mapping.
        return httpx.Response(
            200,
            json={
                "receipts": [
                    {"source_id": "s2", "tx_hash": None, "status": "failed"},
                    {"source_id": "s1", "tx_hash": "0x" + "11" * 32, "status": "settled"},
                ]
            },
        )

    client = httpx.Client(transport=_mock_transport(handler))
    rail = HttpRail()
    monkeypatch.setattr(httpx, "post", lambda url, **kw: client.post(url, **kw))

    receipts = rail.settle(intents)
    assert [r.source_id for r in receipts] == ["s1", "s2"]  # input order preserved
    assert receipts[0].status is SettlementStatus.SETTLED and receipts[0].tx_hash
    assert receipts[1].status is SettlementStatus.FAILED and receipts[1].tx_hash is None


def test_http_rail_empty_intents_no_call() -> None:
    # Empty batch must not hit the network.
    assert HttpRail().settle([]) == []


def test_pipeline_runs_against_http_rail(monkeypatch: pytest.MonkeyPatch) -> None:
    """The agent pipeline works unchanged against HttpRail (the M2 swap)."""

    def handler(request: httpx.Request) -> httpx.Response:
        intents = request.read().decode()
        import json

        parsed = json.loads(intents)["intents"]
        return httpx.Response(
            200,
            json={
                "receipts": [
                    {"source_id": i["source_id"], "tx_hash": "0x" + "22" * 32, "status": "settled"}
                    for i in parsed
                ]
            },
        )

    client = httpx.Client(transport=_mock_transport(handler))
    monkeypatch.setattr(httpx, "post", lambda url, **kw: client.post(url, **kw))

    pipe = AskPipeline(
        store=seeded_registry(),
        rail=HttpRail(),
        signer=AttestationSigner("0x" + "33" * 32),
    )
    result = pipe.ask("How do Gateway nanopayments settle on Arc?", Session(agent_wallet=AUTHOR))
    assert len(result.cited) >= 1
    assert result.total_settled > Decimal(0)
