"""Circle Developer-Controlled Wallets client — REST shapes, polling, retry. No network."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from agent.factory import build_circle_wallets
from shared.circle_wallets import CircleWalletsClient, CircleWalletsError
from shared.config import Settings

CIPHER = "base64-entity-secret-ciphertext"


def _client(handler: Any) -> CircleWalletsClient:
    c = CircleWalletsClient("test-key", client=httpx.Client(transport=httpx.MockTransport(handler)))
    c._sleep = lambda _s: None  # no real delays in polling/retry
    return c


def _router(routes: dict[tuple[str, str], Any]) -> Any:
    """Route (METHOD, path) -> canned JSON (or callable(request)->json). Captures bodies."""
    captured: list[dict[str, Any]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.content:
            captured.append(json.loads(request.content))
        key = (request.method, request.url.path)
        result = routes.get(key)
        if result is None:
            return httpx.Response(404, json={"error": "not found"})
        value = result(request) if callable(result) else result
        if isinstance(value, int):  # a bare status code -> error response
            return httpx.Response(value, json={"message": "err"})
        return httpx.Response(200, json=value)

    _handler.captured = captured  # type: ignore[attr-defined]
    return _handler


def test_create_wallet_set() -> None:
    handler = _router(
        {("POST", "/v1/w3s/developer/walletSets"): {"data": {"walletSet": {"id": "ws_1"}}}}
    )
    ws = _client(handler).create_wallet_set("Keryx", entity_secret_ciphertext=CIPHER)
    assert ws == {"id": "ws_1"}
    body = handler.captured[0]  # type: ignore[attr-defined]
    assert body["name"] == "Keryx" and body["entitySecretCiphertext"] == CIPHER
    assert "idempotencyKey" in body  # auto-generated


def test_create_wallets_defaults_to_arc_sca() -> None:
    handler = _router(
        {
            ("POST", "/v1/w3s/developer/wallets"): {
                "data": {"wallets": [{"id": "w1", "address": "0xabc"}, {"id": "w2"}]}
            }
        }
    )
    wallets = _client(handler).create_wallets("ws_1", entity_secret_ciphertext=CIPHER, count=2)
    assert len(wallets) == 2 and wallets[0]["address"] == "0xabc"
    body = handler.captured[0]  # type: ignore[attr-defined]
    assert body["blockchains"] == ["ARC-TESTNET"] and body["accountType"] == "SCA"
    assert body["count"] == 2 and body["walletSetId"] == "ws_1"


def test_create_contract_execution_returns_tx_id() -> None:
    handler = _router(
        {
            ("POST", "/v1/w3s/developer/transactions/contractExecution"): {
                "data": {"id": "tx_99", "state": "INITIATED"}
            }
        }
    )
    tx_id = _client(handler).create_contract_execution(
        wallet_id="w1",
        contract_address="0xC0n",
        abi_function_signature="register(string)",
        abi_parameters=["ipfs://x"],
        entity_secret_ciphertext=CIPHER,
    )
    assert tx_id == "tx_99"
    body = handler.captured[0]  # type: ignore[attr-defined]
    assert body["abiFunctionSignature"] == "register(string)" and body["feeLevel"] == "MEDIUM"


def test_get_transaction() -> None:
    handler = _router(
        {
            ("GET", "/v1/w3s/transactions/tx_99"): {
                "data": {"transaction": {"state": "COMPLETE", "txHash": "0xhash"}}
            }
        }
    )
    tx = _client(handler).get_transaction("tx_99")
    assert tx["state"] == "COMPLETE" and tx["txHash"] == "0xhash"


def test_wait_for_transaction_polls_until_complete() -> None:
    states = iter(["INITIATED", "PENDING", "COMPLETE"])

    def _tx(_request: httpx.Request) -> dict[str, Any]:
        return {"data": {"transaction": {"state": next(states), "txHash": "0xdone"}}}

    handler = _router({("GET", "/v1/w3s/transactions/tx_99"): _tx})
    assert _client(handler).wait_for_transaction("tx_99", attempts=5) == "0xdone"


def test_wait_for_transaction_raises_on_failed() -> None:
    handler = _router(
        {("GET", "/v1/w3s/transactions/tx_99"): {"data": {"transaction": {"state": "FAILED"}}}}
    )
    with pytest.raises(CircleWalletsError):
        _client(handler).wait_for_transaction("tx_99", attempts=3)


def test_wait_for_transaction_times_out() -> None:
    handler = _router(
        {("GET", "/v1/w3s/transactions/tx_99"): {"data": {"transaction": {"state": "PENDING"}}}}
    )
    with pytest.raises(CircleWalletsError):
        _client(handler).wait_for_transaction("tx_99", attempts=2)


def test_permanent_error_raises_without_retry() -> None:
    calls = {"n": 0}

    def _h(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"message": "bad request"})

    with pytest.raises(CircleWalletsError):
        _client(_h).get_transaction("tx_99")
    assert calls["n"] == 1  # 4xx is permanent -> no retry


def test_transient_error_then_success_retries() -> None:
    calls = {"n": 0}

    def _h(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, json={"message": "busy"})
        return httpx.Response(
            200, json={"data": {"transaction": {"state": "COMPLETE", "txHash": "0xok"}}}
        )

    assert _client(_h).get_transaction("tx_99")["txHash"] == "0xok"
    assert calls["n"] == 3


# --- factory gating ---------------------------------------------------------


def test_build_circle_wallets_disabled_by_default() -> None:
    assert build_circle_wallets(Settings(circle_api_key="")) is None


def test_build_circle_wallets_enabled_with_key() -> None:
    c = build_circle_wallets(Settings(circle_api_key="k"))
    assert isinstance(c, CircleWalletsClient)
    c.close()
