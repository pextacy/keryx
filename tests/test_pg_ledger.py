"""PgLedger — records only settled citations, maps aggregate metrics, recent rows. No DB."""

from __future__ import annotations

from decimal import Decimal

from agent.pg_ledger import PgLedger
from shared.types import CitationRecord
from tests._pg_fakes import FakeDB

CITED = CitationRecord(
    source_url="https://a.com", g=0.8, amount=Decimal("0.004"), tx_hash="0x" + "1" * 64, cited=True
)
NOT_CITED = CitationRecord(source_url="https://b.com", g=0.2, amount=Decimal(0), cited=False)
CITED_NO_TX = CitationRecord(source_url="https://c.com", g=0.9, amount=Decimal("0.005"), cited=True)


def test_record_inserts_only_settled_rows() -> None:
    db = FakeDB()
    PgLedger(db.connect).record(
        query_hash="qh",
        agent_wallet="0xagent",
        citations=[CITED, NOT_CITED, CITED_NO_TX],
        author_wallets={"https://a.com": "0xauthor"},
        external=True,
    )
    inserts = [q for q in db.executed() if "INSERT INTO citations_index" in q]
    assert len(inserts) == 1  # only CITED (cited AND tx_hash); the other two are skipped
    params = db.params_for("INSERT INTO citations_index")
    assert params == [
        "qh",
        "0xagent",
        "https://a.com",
        "0xauthor",
        0.8,
        Decimal("0.004"),
        "0x" + "1" * 64,
        True,
    ]


def test_record_no_qualifying_rows_skips_db() -> None:
    db = FakeDB()
    PgLedger(db.connect).record(
        query_hash="qh",
        agent_wallet="0xagent",
        citations=[NOT_CITED, CITED_NO_TX],
        author_wallets={},
        external=False,
    )
    assert db.calls == []  # nothing settled -> no connection opened


def test_metrics_maps_aggregate_row() -> None:
    # total, citations, authors, sessions, ext_cit, ext_total, team_cit, team_total
    row = ("0.012000", 3, 2, 2, 1, "0.004000", 2, "0.008000")
    db = FakeDB(lambda q, p: [row] if "FROM citations_index" in q else [])
    m = PgLedger(db.connect).metrics()
    assert m["total_settled_usdc"] == "0.012000"
    assert m["citations_settled"] == 3
    assert m["distinct_author_wallets"] == 2
    assert m["distinct_sessions"] == 2
    assert m["external"] == {"citations": 1, "settled_usdc": "0.004000"}
    assert m["team"] == {"citations": 2, "settled_usdc": "0.008000"}
    assert m["external_share_pct"] == round(100 * 1 / 3, 1)


def test_metrics_empty_ledger() -> None:
    db = FakeDB(lambda q, p: [("0", 0, 0, 0, 0, "0", 0, "0")])
    m = PgLedger(db.connect).metrics()
    assert m["citations_settled"] == 0 and m["external_share_pct"] == 0.0


def test_recent_maps_rows() -> None:
    rows = [("https://a.com", "0xauthor", 0.8, "0.004000", "0x" + "1" * 64, True, 1700000000)]
    db = FakeDB(lambda q, p: rows if "ORDER BY ts DESC" in q else [])
    out = PgLedger(db.connect).recent(limit=10)
    assert out == [
        {
            "source_url": "https://a.com",
            "author_wallet": "0xauthor",
            "g": 0.8,
            "amount": "0.004000",
            "tx_hash": "0x" + "1" * 64,
            "external": True,
            "ts": 1700000000,
        }
    ]
    assert db.params_for("ORDER BY ts DESC") == [10]
