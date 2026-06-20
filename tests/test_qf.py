"""Quadratic funding — breadth-weighted match, dust-free pool, /qf settlement (PA 03/07)."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

import agent.main as main
from shared.qf import Project, match_weight, quadratic_match

A = "0x" + "a" * 40
B = "0x" + "b" * 40
C = "0x" + "c" * 40


def test_weight_is_sqrt_sum_squared() -> None:
    # four backers of 1 -> (4)^2 = 16 ; one backer of 4 -> (2)^2 = 4.
    assert match_weight([Decimal(1)] * 4) == Decimal("16")
    assert match_weight([Decimal(4)]) == Decimal("4")


def test_breadth_beats_size_and_sums_to_pool() -> None:
    projects = [Project(A, [Decimal(1)] * 4), Project(B, [Decimal(4)])]
    pairs = quadratic_match(Decimal("0.01"), projects)
    match = {p.wallet: amt for p, amt in pairs}
    # 16:4 -> 0.008 vs 0.002; broad support wins despite equal direct totals.
    assert match[A] == Decimal("0.008") and match[B] == Decimal("0.002")
    assert sum(match.values()) == Decimal("0.01")


def test_zero_contribution_project_gets_nothing() -> None:
    pairs = quadratic_match(Decimal("0.01"), [Project(A, [Decimal(1)]), Project(B, [])])
    match = {p.wallet: amt for p, amt in pairs}
    assert match[B] == Decimal(0) and match[A] == Decimal("0.01")


# --- endpoint ---------------------------------------------------------------


def _client() -> TestClient:
    return TestClient(main.app)


def test_qf_endpoint_settles_matches() -> None:
    body = {
        "pool": "0.01",
        "projects": [
            {"wallet": A, "contributions": ["1", "1", "1", "1"]},
            {"wallet": B, "contributions": ["4"]},
        ],
    }
    res = _client().post("/qf", json=body).json()
    match = {p["wallet"]: p["match"] for p in res["projects"]}
    assert match == {A: "0.008000", B: "0.002000"}
    assert res["total_matched"] == "0.010000"
    backers = {p["wallet"]: p["backers"] for p in res["projects"]}
    assert backers == {A: 4, B: 1}
    assert all(p["settled"] for p in res["projects"])


def test_qf_rejects_bad_wallet() -> None:
    res = _client().post(
        "/qf", json={"pool": "0.01", "projects": [{"wallet": "x", "contributions": ["1"]}]}
    )
    assert res.status_code == 422
