"""End-to-end citation loop against the mock rail + registry fixtures."""

from __future__ import annotations

from decimal import Decimal

from agent.attestation import AttestationSigner, verify_attestation
from agent.pipeline import AskPipeline, Session
from registry import parse_dataitems, seeded_registry
from shared.rail import MockRail
from shared.types import SettlementStatus

KEY = "0x" + "22" * 32
QUERY = "How do Gateway nanopayments settle sub-cent USDC payments on Arc?"


def _pipeline(rail: MockRail | None = None) -> AskPipeline:
    return AskPipeline(
        store=seeded_registry(),
        rail=rail or MockRail(),
        signer=AttestationSigner(KEY),
    )


def test_ask_cites_and_skips_visibly() -> None:
    result = _pipeline().ask(QUERY, Session(agent_wallet="0x" + "00" * 20))
    # DoD: >=1 cited and >=1 evaluated-but-not-cited (the off-topic source).
    assert len(result.cited) >= 1
    assert len(result.evaluated_not_cited) >= 1
    assert result.total_settled > Decimal(0)
    # Cited records carry a real tx + amount; skipped ones are $0 with no tx.
    for c in result.cited:
        assert c.tx_hash and c.amount > Decimal(0)
    for c in result.evaluated_not_cited:
        assert c.tx_hash is None and c.amount == Decimal(0)


def test_attestation_is_signed_and_verifiable() -> None:
    result = _pipeline().ask(QUERY, Session(agent_wallet="0x" + "00" * 20))
    assert verify_attestation(result.attestation)
    assert result.attestation.agent_pubkey == AttestationSigner(KEY).address


def test_budget_caps_settlement() -> None:
    # Tiny budget: at most one citation should settle.
    session = Session(agent_wallet="0x" + "00" * 20, budget_total=Decimal("0.001"))
    result = _pipeline().ask(QUERY, session)
    assert result.total_settled <= Decimal("0.001")
    assert session.budget_spent == result.total_settled


def test_total_settled_matches_cited_sum() -> None:
    result = _pipeline().ask(QUERY, Session(agent_wallet="0x" + "00" * 20))
    assert result.total_settled == sum(c.amount for c in result.cited)


def test_failed_settlement_recorded_as_not_cited() -> None:
    reg = seeded_registry()
    # Force every settlement to fail; nothing should count as cited/paid.
    rail = MockRail(fail_source_ids={s.source_id for s in reg.all()})
    pipe = AskPipeline(store=reg, rail=rail, signer=AttestationSigner(KEY))
    result = pipe.ask(QUERY, Session(agent_wallet="0x" + "00" * 20))
    assert result.total_settled == Decimal(0)
    assert all(not c.cited for c in result.citations)


def test_rsshub_dataitem_ingest() -> None:
    items = [
        {
            "link": "https://x.com/p1",
            "author": "alice",
            "title": "T",
            "description": "<p>hello</p>",
        },
        {"author": "nolink"},  # dropped: no canonical link
    ]
    sources = parse_dataitems(items, lambda a: "0x" + "11" * 20 if a == "alice" else None)
    assert len(sources) == 1
    assert sources[0].url == "https://x.com/p1"
    assert sources[0].author_wallet == "0x" + "11" * 20
    assert "hello" in sources[0].text and "<" not in sources[0].text


def test_settlement_status_enum_values() -> None:
    assert SettlementStatus.SETTLED == "settled"
