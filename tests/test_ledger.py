"""Settlement ledger + traction metrics, incl. team-vs-external split."""

from __future__ import annotations

from decimal import Decimal

from agent.ledger import Ledger
from shared.types import CitationRecord

A1 = "0x" + "11" * 20
A2 = "0x" + "22" * 20
TX = "0x" + "ab" * 32


def _cite(url: str, amount: str, cited: bool = True) -> CitationRecord:
    return CitationRecord(
        source_url=url,
        g=0.7 if cited else 0.1,
        amount=Decimal(amount),
        tx_hash=TX if cited else None,
        cited=cited,
    )


def test_ledger_records_only_settled() -> None:
    led = Ledger()
    led.record(
        query_hash="q1",
        agent_wallet="0x" + "00" * 20,
        citations=[_cite("https://a", "0.005"), _cite("https://b", "0", cited=False)],
        author_wallets={"https://a": A1, "https://b": A2},
        external=False,
    )
    assert len(led.entries) == 1  # the $0 skip is not ledgered
    assert led.metrics()["citations_settled"] == 1


def test_team_vs_external_split() -> None:
    led = Ledger()
    led.record(
        query_hash="q1",
        agent_wallet="0xteam",
        citations=[_cite("https://a", "0.005")],
        author_wallets={"https://a": A1},
        external=False,
    )
    led.record(
        query_hash="q2",
        agent_wallet="0xext",
        citations=[_cite("https://b", "0.003")],
        author_wallets={"https://b": A2},
        external=True,
    )
    m = led.metrics()
    assert m["citations_settled"] == 2
    assert m["distinct_author_wallets"] == 2
    assert m["distinct_sessions"] == 2
    assert m["total_settled_usdc"] == "0.008"
    assert m["team"]["citations"] == 1 and m["external"]["citations"] == 1
    assert m["external_share_pct"] == 50.0


def test_recent_is_capped_and_newest_first() -> None:
    led = Ledger()
    for i in range(5):
        led.record(
            query_hash=f"q{i}",
            agent_wallet="0xteam",
            citations=[_cite(f"https://s{i}", "0.001")],
            author_wallets={f"https://s{i}": A1},
            external=False,
        )
    assert len(led.recent(limit=3)) == 3
