"""Reputation bonds — post/resolve state machine + /bond slash settlement."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import agent.main as main
from shared.bonds import BondAlreadyResolved, BondBook, BondStatus

PROVIDER = "0x" + "1" * 40
CLAIMANT = "0x" + "2" * 40


def test_post_and_get() -> None:
    book = BondBook()
    b = book.post(provider=PROVIDER, amount=Decimal("0.01"), claimant=CLAIMANT)
    assert b.status is BondStatus.POSTED and b.id == "bond:1"
    assert book.get("bond:1") == b


def test_release_on_pass() -> None:
    book = BondBook()
    book.post(provider=PROVIDER, amount=Decimal("0.01"), claimant=CLAIMANT)
    r = book.resolve("bond:1", passed=True)
    assert r.status is BondStatus.RELEASED and r.reputation_delta == 100


def test_slash_on_fail() -> None:
    book = BondBook()
    book.post(provider=PROVIDER, amount=Decimal("0.01"), claimant=CLAIMANT)
    r = book.resolve("bond:1", passed=False)
    assert r.status is BondStatus.SLASHED and r.reputation_delta == -100


def test_double_resolve_guarded() -> None:
    book = BondBook()
    book.post(provider=PROVIDER, amount=Decimal("0.01"), claimant=CLAIMANT)
    book.resolve("bond:1", passed=True)
    with pytest.raises(BondAlreadyResolved):
        book.resolve("bond:1", passed=False)


def test_resolve_unknown_raises() -> None:
    with pytest.raises(KeyError):
        BondBook().resolve("bond:404", passed=True)


# --- endpoints --------------------------------------------------------------


def _client() -> TestClient:
    return TestClient(main.app)


def test_bond_lifecycle_slash_settles_to_claimant() -> None:
    c = _client()
    posted = c.post(
        "/bond", json={"provider": PROVIDER, "claimant": CLAIMANT, "amount": "0.01"}
    ).json()
    bid = posted["bond_id"]
    assert posted["status"] == "posted"
    resolved = c.post(f"/bond/{bid}/resolve", json={"passed": False}).json()
    assert resolved["status"] == "slashed"
    assert resolved["reputation_delta"] == -100
    assert resolved["tx_hash"]  # the bond settled to the claimant via MockRail


def test_bond_release_has_no_settlement() -> None:
    c = _client()
    bid = c.post(
        "/bond", json={"provider": PROVIDER, "claimant": CLAIMANT, "amount": "0.01"}
    ).json()["bond_id"]
    resolved = c.post(f"/bond/{bid}/resolve", json={"passed": True}).json()
    assert resolved["status"] == "released" and resolved["tx_hash"] is None


def test_bond_rejects_bad_wallet() -> None:
    res = _client().post("/bond", json={"provider": "nope", "claimant": CLAIMANT, "amount": "0.01"})
    assert res.status_code == 422


def test_resolve_unknown_bond_returns_not_found() -> None:
    res = _client().post("/bond/bond:999/resolve", json={"passed": True}).json()
    assert res["found"] is False
