"""Streaming payments — per-second billing with fractional carry + /stream settlement."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import agent.main as main
from shared.streaming import StreamBook, StreamClosed, StreamStatus

PAYER = "0x" + "1" * 40
PAYEE = "0x" + "2" * 40


def test_tick_bills_rate_times_seconds() -> None:
    book = StreamBook()
    book.open(payer=PAYER, payee=PAYEE, rate=Decimal("0.001"))
    assert book.tick("stream:1", Decimal(2)) == Decimal("0.002")


def test_sub_micro_fraction_carries_no_dust() -> None:
    book = StreamBook()
    # 0.0000015/s: tick 1 -> 0.0000015 accrued -> bill 0.000001 (carry 0.0000005).
    book.open(payer=PAYER, payee=PAYEE, rate=Decimal("0.0000015"))
    first = book.tick("stream:1", Decimal(1))
    book.commit("stream:1", first)  # rail cleared -> advance settled
    second = book.tick("stream:1", Decimal(1))  # accrued 0.000003 -> bill 0.000002
    assert first == Decimal("0.000001") and second == Decimal("0.000002")
    assert first + second == Decimal("0.000003")  # exact, no dust


def test_unsettled_tick_is_rebilled_not_lost() -> None:
    # The core bug fix: tick() reports what's owed but does NOT advance `settled`. If the
    # caller's rail settlement fails (no commit), the same amount is re-billed next time
    # instead of being silently marked paid and lost to the payee.
    book = StreamBook()
    book.open(payer=PAYER, payee=PAYEE, rate=Decimal("0.001"))
    due = book.tick("stream:1", Decimal(2))  # 0.002 owed
    again = book.tick("stream:1", Decimal(0))  # no new flow, not committed -> still owed
    assert due == Decimal("0.002") and again == Decimal("0.002")
    book.commit("stream:1", again)  # now it clears
    assert book.tick("stream:1", Decimal(0)) == Decimal(0)  # nothing left owed


def test_paused_stream_accrues_nothing() -> None:
    book = StreamBook()
    book.open(payer=PAYER, payee=PAYEE, rate=Decimal("0.001"))
    book.pause("stream:1")
    assert book.tick("stream:1", Decimal(10)) == Decimal(0)
    assert book.resume("stream:1").status is StreamStatus.OPEN
    assert book.tick("stream:1", Decimal(1)) == Decimal("0.001")


def test_close_returns_final_and_blocks_further_ops() -> None:
    book = StreamBook()
    book.open(payer=PAYER, payee=PAYEE, rate=Decimal("0.001"))
    due1 = book.tick("stream:1", Decimal(1))
    book.commit("stream:1", due1)  # rail cleared -> advance settled
    _s, due = book.close("stream:1")
    assert due == Decimal(0)  # nothing left after the committed tick
    with pytest.raises(StreamClosed):
        book.tick("stream:1", Decimal(1))


# --- endpoints --------------------------------------------------------------


def _client() -> TestClient:
    return TestClient(main.app)


def test_stream_endpoint_settles_each_tick() -> None:
    c = _client()
    sid = c.post("/stream", json={"payer": PAYER, "payee": PAYEE, "rate": "0.001"}).json()[
        "stream_id"
    ]
    t1 = c.post(f"/stream/{sid}/tick", json={"seconds": "3"}).json()
    assert t1["billed"] == "0.003000" and t1["tx_hash"]
    assert t1["total_settled"] == "0.003000"
    closed = c.post(f"/stream/{sid}/close", json={}).json()
    assert closed["status"] == "closed"


def test_stream_pause_resume_endpoints() -> None:
    c = _client()
    sid = c.post("/stream", json={"payer": PAYER, "payee": PAYEE, "rate": "0.001"}).json()[
        "stream_id"
    ]
    assert c.post(f"/stream/{sid}/pause").json()["status"] == "paused"
    paused_tick = c.post(f"/stream/{sid}/tick", json={"seconds": "5"}).json()
    assert paused_tick["billed"] == "0.000000" and paused_tick["tx_hash"] is None
    assert c.post(f"/stream/{sid}/resume").json()["status"] == "open"


def test_stream_rejects_bad_wallet() -> None:
    res = _client().post("/stream", json={"payer": "nope", "payee": PAYEE, "rate": "0.001"})
    assert res.status_code == 422


def test_tick_unknown_stream_not_found() -> None:
    assert _client().post("/stream/stream:999/tick", json={"seconds": "1"}).json()["found"] is False
