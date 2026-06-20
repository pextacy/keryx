"""User-centric royalties — budget split by real plays, with play-gating (PA 05)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import agent.main as main

A = "0x" + "a" * 40
B = "0x" + "b" * 40
C = "0x" + "c" * 40


def _client() -> TestClient:
    return TestClient(main.app)


def test_splits_budget_by_play_counts() -> None:
    body = {"budget": "0.01", "plays": [{"wallet": A, "count": 30}, {"wallet": B, "count": 10}]}
    res = _client().post("/royalties", json=body).json()
    amounts = {r["wallet"]: r["amount"] for r in res["recipients"]}
    assert amounts == {A: "0.007500", B: "0.002500"}  # 3:1 by plays
    assert res["total_settled"] == "0.010000" and res["gated_out"] == 0
    assert all(r["settled"] for r in res["recipients"])


def test_play_gating_drops_sub_threshold() -> None:
    body = {
        "budget": "0.01",
        "plays": [{"wallet": A, "count": 5}, {"wallet": B, "count": 0}],
        "min_count": 1,
    }
    res = _client().post("/royalties", json=body).json()
    assert [r["wallet"] for r in res["recipients"]] == [A]  # B gated out (0 plays)
    assert res["gated_out"] == 1 and res["recipients"][0]["amount"] == "0.010000"


def test_all_gated_out_settles_nothing() -> None:
    body = {"budget": "0.01", "plays": [{"wallet": A, "count": 0}], "min_count": 1}
    res = _client().post("/royalties", json=body).json()
    assert res["recipients"] == [] and res["total_settled"] == "0" and res["gated_out"] == 1


def test_rejects_bad_wallet() -> None:
    res = _client().post(
        "/royalties", json={"budget": "0.01", "plays": [{"wallet": "x", "count": 1}]}
    )
    assert res.status_code == 422
