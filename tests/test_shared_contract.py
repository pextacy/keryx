"""Phase 0 DoD: the frozen shared/ contract is importable from both sides and works.

Exercises the contract the way CC-A (rail) and CC-B (agent) each will, plus the
MockRail round-trip and the validation guarantees that make the types safe to share.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from shared import (
    Attestation,
    CitationIntent,
    CitationRecord,
    MockRail,
    Rail,
    Receipt,
    SettlementStatus,
    settings,
)

AUTHOR = "0x" + "ab" * 20
AGENT = "0x" + "cd" * 20


def test_types_importable_from_shared() -> None:
    # Both instances import the same frozen names from the same place.
    assert CitationIntent and Receipt and Attestation and CitationRecord


def test_citation_intent_validates_wallet_and_amount() -> None:
    intent = CitationIntent(source_id="s1", author_wallet=AUTHOR, amount=Decimal("0.001"))
    assert intent.amount == Decimal("0.001")

    with pytest.raises(ValidationError):
        CitationIntent(source_id="s1", author_wallet="not-an-address", amount=Decimal("0.001"))

    with pytest.raises(ValidationError):  # below the USDC floor
        CitationIntent(source_id="s1", author_wallet=AUTHOR, amount=Decimal("0.0000001"))


def test_models_are_frozen() -> None:
    intent = CitationIntent(source_id="s1", author_wallet=AUTHOR, amount=Decimal("0.001"))
    with pytest.raises(ValidationError):
        intent.amount = Decimal("0.002")  # type: ignore[misc]


def test_mockrail_satisfies_protocol_and_round_trips() -> None:
    rail: Rail = MockRail()
    assert isinstance(rail, Rail)

    intents = [
        CitationIntent(source_id="s1", author_wallet=AUTHOR, amount=Decimal("0.001")),
        CitationIntent(source_id="s2", author_wallet=AUTHOR, amount=Decimal("0.005")),
    ]
    receipts = rail.settle(intents)

    assert len(receipts) == len(intents)
    assert [r.source_id for r in receipts] == ["s1", "s2"]
    assert all(r.status is SettlementStatus.SETTLED for r in receipts)
    assert all(r.tx_hash and r.tx_hash.startswith("0x") and len(r.tx_hash) == 66 for r in receipts)


def test_mockrail_is_deterministic() -> None:
    intent = CitationIntent(source_id="s1", author_wallet=AUTHOR, amount=Decimal("0.001"))
    a = MockRail().settle([intent])[0]
    b = MockRail().settle([intent])[0]
    assert a.tx_hash == b.tx_hash


def test_mockrail_failure_path() -> None:
    rail = MockRail(fail_source_ids={"s2"})
    intents = [
        CitationIntent(source_id="s1", author_wallet=AUTHOR, amount=Decimal("0.001")),
        CitationIntent(source_id="s2", author_wallet=AUTHOR, amount=Decimal("0.001")),
    ]
    r1, r2 = rail.settle(intents)
    assert r1.status is SettlementStatus.SETTLED and r1.tx_hash
    assert r2.status is SettlementStatus.FAILED and r2.tx_hash is None


def test_attestation_holds_cited_and_evaluated_not_cited() -> None:
    tx = "0x" + "11" * 32
    att = Attestation(
        query_hash="qh",
        answer_hash="ah",
        agent_pubkey=AGENT,
        ts=1_750_000_000,
        citations=(
            CitationRecord(source_url="https://a", g=0.8, amount=Decimal("0.005"), tx_hash=tx),
            # evaluated-but-not-cited: $0, no tx — the visible gating prd.md requires.
            CitationRecord(source_url="https://b", g=0.2, amount=Decimal(0), cited=False),
        ),
    )
    cited = [c for c in att.citations if c.cited]
    not_cited = [c for c in att.citations if not c.cited]
    assert len(cited) == 1 and len(not_cited) == 1
    assert not_cited[0].amount == Decimal(0) and not_cited[0].tx_hash is None


def test_config_defaults_match_spec() -> None:
    assert settings.usdc_floor == Decimal("0.000001")
    assert settings.citation_toll_min == Decimal("0.001")
    assert settings.citation_toll_max == Decimal("0.01")
    assert settings.grounding_threshold == 0.5
