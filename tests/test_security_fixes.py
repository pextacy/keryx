"""Regression tests for the hardening pass: input bounds, auth, body limit, dust math.

Each test pins a specific fix so a future change that regresses it fails loudly.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import agent.main as main
from shared.qf import Project, match_weight, quadratic_match
from shared.splits import split_amount

A = "0x" + "a" * 40
B = "0x" + "b" * 40


def _client() -> TestClient:
    return TestClient(main.app)


# --- M1: split_amount rejects a negative total (would break the dust-free invariant) ---


def test_split_amount_rejects_negative_total() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        split_amount(Decimal("-0.000005"), [Decimal(1), Decimal(1)])


def test_split_amount_zero_total_is_all_zero() -> None:
    assert split_amount(Decimal(0), [Decimal(2), Decimal(1)]) == [Decimal(0), Decimal(0)]


# --- Retro impact: O(1) weight (no giant list) and a sane upper bound ---


def test_retro_impact_weight_matches_unit_contributions() -> None:
    # weight must equal (Σ√1 over `impact`)² == impact², which impact² as one contribution gives.
    impact = 50
    assert match_weight([Decimal(impact) ** 2]) == match_weight([Decimal(1)] * impact)


def test_retro_endpoint_rejects_absurd_impact() -> None:
    res = _client().post(
        "/retro", json={"pool": "0.01", "projects": [{"wallet": A, "impact": 10_000_001}]}
    )
    assert res.status_code == 422


def test_retro_endpoint_handles_large_in_bound_impact_fast() -> None:
    # A large-but-allowed impact must not materialise a list of that length.
    res = (
        _client()
        .post(
            "/retro",
            json={"pool": "0.01", "projects": [{"wallet": A, "impact": 9_000_000}]},
        )
        .json()
    )
    assert res["projects"][0]["settled"] is True


# --- Validation: list length is bounded ---


def test_payout_rejects_oversized_contributor_list() -> None:
    body = {"amount": "0.01", "contributors": [{"wallet": A, "share": 1}] * 1001}
    assert _client().post("/payout", json=body).status_code == 422


# --- C2: bearer auth gates mutations when configured; reads stay open ---


def test_auth_blocks_mutation_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main.settings, "api_token", "s3cret")
    body = {"amount": "0.01", "contributors": [{"wallet": A, "share": 1}]}
    assert _client().post("/payout", json=body).status_code == 401


def test_auth_allows_mutation_with_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main.settings, "api_token", "s3cret")
    body = {"amount": "0.01", "contributors": [{"wallet": A, "share": 1}]}
    res = _client().post("/payout", json=body, headers={"Authorization": "Bearer s3cret"})
    assert res.status_code == 200


def test_reads_open_even_with_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main.settings, "api_token", "s3cret")
    assert _client().get("/healthz").status_code == 200


def test_no_auth_when_token_unset() -> None:
    # Default demo posture: no token configured -> mutations work with no header.
    body = {"amount": "0.01", "contributors": [{"wallet": A, "share": 1}]}
    assert _client().post("/payout", json=body).status_code == 200


# --- Body-size limit ---


def test_oversized_body_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main.settings, "max_body_bytes", 10)
    body = {"amount": "0.01", "contributors": [{"wallet": A, "share": 1}]}
    assert _client().post("/payout", json=body).status_code == 413


# --- quadratic_match still sums exactly (guard against the impact refactor drifting) ---


def test_quadratic_match_still_dust_free() -> None:
    projects = [Project(A, [Decimal(1)] * 4), Project(B, [Decimal(4)])]
    pairs = quadratic_match(Decimal("0.01"), projects)
    assert sum(amt for _, amt in pairs) == Decimal("0.01")
