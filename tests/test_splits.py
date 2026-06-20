"""Royalty splits — exact, dust-free apportionment + the /payout settlement endpoint."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import agent.main as main
from shared.splits import Contributor, split_amount, split_payout

W1 = "0x" + "1" * 40
W2 = "0x" + "2" * 40
W3 = "0x" + "3" * 40


def test_even_split_sums_exactly() -> None:
    parts = split_amount(Decimal("0.009"), [Decimal(1), Decimal(1), Decimal(1)])
    assert parts == [Decimal("0.003"), Decimal("0.003"), Decimal("0.003")]
    assert sum(parts) == Decimal("0.009")


def test_indivisible_amount_has_no_dust() -> None:
    # 0.000007 USDC across 3 equal weights -> 7 micro-units -> 3/2/2, sums exactly.
    parts = split_amount(Decimal("0.000007"), [Decimal(1), Decimal(1), Decimal(1)])
    assert sum(parts) == Decimal("0.000007")
    assert sorted(parts, reverse=True) == [
        Decimal("0.000003"),
        Decimal("0.000002"),
        Decimal("0.000002"),
    ]


def test_weighted_split_is_proportional_and_exact() -> None:
    # 60/30/10 of 0.01 USDC.
    parts = split_amount(Decimal("0.01"), [Decimal(60), Decimal(30), Decimal(10)])
    assert parts == [Decimal("0.006"), Decimal("0.003"), Decimal("0.001")]
    assert sum(parts) == Decimal("0.01")


def test_never_overpays_truncates_to_micro_usdc() -> None:
    # Sub-micro precision in the total is dropped (ROUND_DOWN), never rounded up.
    parts = split_amount(Decimal("0.0000015"), [Decimal(1)])
    assert parts == [Decimal("0.000001")]


def test_largest_remainder_goes_to_biggest_fraction() -> None:
    # 0.000010 split 1:1:1 -> 4/3/3 micro; the extra unit goes to one share.
    parts = split_amount(Decimal("0.00001"), [Decimal(1), Decimal(1), Decimal(1)])
    assert sum(parts) == Decimal("0.00001")
    assert max(parts) == Decimal("0.000004")


def test_rejects_nonpositive_or_empty_weights() -> None:
    with pytest.raises(ValueError):
        split_amount(Decimal("0.01"), [])
    with pytest.raises(ValueError):
        split_amount(Decimal("0.01"), [Decimal(1), Decimal(0)])


def test_split_payout_pairs_contributors() -> None:
    pairs = split_payout(
        Decimal("0.01"), [Contributor(W1, Decimal(3)), Contributor(W2, Decimal(1))]
    )
    assert [(c.wallet, amt) for c, amt in pairs] == [
        (W1, Decimal("0.0075")),
        (W2, Decimal("0.0025")),
    ]


# --- /payout endpoint -------------------------------------------------------


def _client() -> TestClient:
    return TestClient(main.app)


def test_payout_settles_each_share() -> None:
    body = {
        "amount": "0.01",
        "contributors": [
            {"wallet": W1, "share": "3"},
            {"wallet": W2, "share": "1"},
        ],
    }
    res = _client().post("/payout", json=body).json()
    assert res["amount"] == "0.01"
    amounts = {r["wallet"]: r["amount"] for r in res["recipients"]}
    assert amounts == {W1: "0.007500", W2: "0.002500"}  # canonical 6-dp USDC
    assert all(r["settled"] and r["tx_hash"] for r in res["recipients"])  # MockRail settles
    assert res["total_settled"] == "0.010000"  # shares sum back to the total, no dust


def test_payout_rejects_bad_wallet() -> None:
    res = _client().post(
        "/payout", json={"amount": "0.01", "contributors": [{"wallet": "nope", "share": "1"}]}
    )
    assert res.status_code == 422


def test_payout_requires_a_contributor() -> None:
    assert _client().post("/payout", json={"amount": "0.01", "contributors": []}).status_code == 422
