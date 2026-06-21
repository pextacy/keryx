"""Gateway unified balance — deposit, spend, and cross-chain transfer (arc-multichain-wallet).

The transfer path ports arc-multichain-wallet's burn/mint move: funds leave the unified
balance to a destination chain (optionally to an external recipient), drawn down dust-free.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import agent.main as main
from shared.gateway import GatewayBook, GatewayError, normalize_chain

WALLET = "0x" + "a" * 40
RECIPIENT = "0x" + "b" * 40


def test_normalize_chain_is_case_insensitive() -> None:
    assert normalize_chain("ARCTESTNET") == "arcTestnet"
    assert normalize_chain("baseSepolia") == "baseSepolia"


def test_unknown_chain_rejected() -> None:
    book = GatewayBook()
    with pytest.raises(GatewayError):
        book.deposit(WALLET, "ethereum", Decimal("1"))


def test_deposit_credits_unified_balance_with_chain_provenance() -> None:
    book = GatewayBook()
    book.deposit(WALLET, "avalancheFuji", Decimal("0.5"), tx_hash="0xdep")
    acct = book.deposit(WALLET, "baseSepolia", Decimal("0.25"))
    assert acct.balance == Decimal("0.75")
    assert acct.by_chain == {"avalancheFuji": Decimal("0.5"), "baseSepolia": Decimal("0.25")}


def test_transfer_draws_down_balance_and_records_withdrawal() -> None:
    book = GatewayBook()
    book.deposit(WALLET, "avalancheFuji", Decimal("1.0"))
    amount = book.prepare_transfer(WALLET, "baseSepolia", Decimal("0.4"))
    assert amount == Decimal("0.4")
    acct = book.settled_transfer(WALLET, amount, "baseSepolia", RECIPIENT, tx_hash="0xmint")
    assert acct.balance == Decimal("0.6")
    assert len(acct.withdrawals) == 1
    w = acct.withdrawals[0]
    assert w.chain == "baseSepolia" and w.recipient == RECIPIENT and w.tx_hash == "0xmint"
    assert w.amount == Decimal("0.4")


def test_transfer_over_balance_is_rejected_and_nothing_drawn() -> None:
    book = GatewayBook()
    book.deposit(WALLET, "arcTestnet", Decimal("0.10"))
    with pytest.raises(GatewayError):
        book.prepare_transfer(WALLET, "baseSepolia", Decimal("0.25"))
    assert book.account(WALLET).balance == Decimal("0.10")  # untouched


def test_transfer_to_unknown_destination_chain_rejected() -> None:
    book = GatewayBook()
    book.deposit(WALLET, "arcTestnet", Decimal("1"))
    with pytest.raises(GatewayError):
        book.prepare_transfer(WALLET, "polygon", Decimal("0.1"))


# --- endpoint-level (mock rail) ---


@pytest.fixture()
def client() -> TestClient:
    return TestClient(main.app)


def test_transfer_endpoint_moves_funds_cross_chain(client: TestClient) -> None:
    # Distinct wallet per endpoint test — the app holds one process-wide gateway book.
    wallet = "0x" + "c" * 40
    client.post(
        "/gateway/deposit", json={"wallet": wallet, "chain": "avalancheFuji", "amount": "0.5"}
    )
    res = client.post(
        "/gateway/transfer",
        json={
            "wallet": wallet,
            "destination_chain": "baseSepolia",
            "amount": "0.2",
            "recipient": RECIPIENT,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["transferred"] is True
    assert body["destination_chain"] == "baseSepolia"
    assert body["recipient"] == RECIPIENT
    assert body["tx_hash"].startswith("0x")
    assert body["balance"] == "0.300000"
    assert body["withdrawals"][0]["chain"] == "baseSepolia"


def test_transfer_endpoint_defaults_recipient_to_self(client: TestClient) -> None:
    wallet = "0x" + "d" * 40
    client.post("/gateway/deposit", json={"wallet": wallet, "chain": "arcTestnet", "amount": "0.3"})
    res = client.post(
        "/gateway/transfer",
        json={"wallet": wallet, "destination_chain": "arcTestnet", "amount": "0.1"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["recipient"] == wallet


def test_transfer_endpoint_insufficient_balance_errors(client: TestClient) -> None:
    wallet = "0x" + "e" * 40
    client.post(
        "/gateway/deposit", json={"wallet": wallet, "chain": "arcTestnet", "amount": "0.05"}
    )
    res = client.post(
        "/gateway/transfer",
        json={"wallet": wallet, "destination_chain": "baseSepolia", "amount": "0.5"},
    )
    assert res.status_code == 200, res.text
    assert "insufficient_balance" in res.json()["error"]
