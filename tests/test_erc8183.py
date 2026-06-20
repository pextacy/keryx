"""ERC-8183 AgenticCommerce client — job tuple decode, lifecycle writes. No network."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx
import pytest
from eth_abi import encode as abi_encode

from agent.factory import build_erc8183
from shared.chain import JsonRpcClient
from shared.config import Settings
from shared.erc8183 import (
    _JOB_CREATED_TOPIC,
    _JOB_TUPLE,
    Erc8183Client,
    Job,
    JobStatus,
)

CONTRACT = "0x0747EEf0706327138c69792bF28Cd525089e4583"
USDC = "0x3600000000000000000000000000000000000000"
TEST_KEY = "0x" + "1" * 64
A = "0x" + "a" * 40
B = "0x" + "b" * 40


def _client(handler: Any, *, key: str | None = None) -> Erc8183Client:
    rpc = JsonRpcClient(
        "http://rpc.local", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    return Erc8183Client(
        rpc, contract=CONTRACT, usdc_address=USDC, chain_id=0x4CEF52, private_key=key
    )


def _rpc_router(routes: dict[str, Any]) -> Any:
    captured: list[dict[str, Any]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured.append(body)
        result = routes.get(body["method"])
        value = result(body["params"]) if callable(result) else result
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": value})

    _handler.captured = captured  # type: ignore[attr-defined]
    return _handler


def _job_call_result() -> str:
    job = (7, A, B, A, "research job", 5_000_000, 9999, 3, "0x" + "0" * 40)
    return "0x" + abi_encode([_JOB_TUPLE], [job]).hex()


def test_job_status_enum() -> None:
    assert JobStatus.OPEN == 0 and JobStatus.COMPLETED == 3 and JobStatus.EXPIRED == 5


def test_get_job_decodes_tuple() -> None:
    client = _client(_rpc_router({"eth_call": _job_call_result()}))
    j = client.get_job(7)
    assert isinstance(j, Job)
    assert j.id == 7 and j.status is JobStatus.COMPLETED
    assert j.budget == Decimal("5") and j.description == "research job"
    assert j.client.lower() == A and j.provider.lower() == B


def test_get_job_none_when_empty() -> None:
    assert _client(_rpc_router({"eth_call": "0x"})).get_job(7) is None


def test_job_id_from_receipt() -> None:
    receipt = {
        "logs": [{"address": CONTRACT, "topics": [_JOB_CREATED_TOPIC, "0x" + format(42, "064x")]}]
    }
    client = _client(_rpc_router({"eth_getTransactionReceipt": receipt}))
    assert client.job_id_from_receipt("0xtx") == 42


def test_job_id_from_receipt_none_without_event() -> None:
    receipt = {"logs": [{"address": "0x" + "9" * 40, "topics": ["0xdead"]}]}
    assert (
        _client(_rpc_router({"eth_getTransactionReceipt": receipt})).job_id_from_receipt("0xtx")
        is None
    )


def test_write_without_key_raises() -> None:
    client = _client(_rpc_router({}))
    assert not client.can_write
    with pytest.raises(RuntimeError):
        client.create_job(B, A, 9999, "x")


def _write_router() -> Any:
    return _rpc_router(
        {
            "eth_getTransactionCount": "0x0",
            "eth_gasPrice": "0x1",
            "eth_sendRawTransaction": "0x" + "d" * 64,
        }
    )


def test_full_lifecycle_writes_send_signed_txs() -> None:
    handler = _write_router()
    c = _client(handler, key=TEST_KEY)
    assert c.create_job(B, A, 9999, "research job") == "0x" + "d" * 64
    assert c.set_budget(7, Decimal("5")) == "0x" + "d" * 64
    assert c.approve_usdc(Decimal("5")) == "0x" + "d" * 64
    assert c.fund(7) == "0x" + "d" * 64
    assert c.submit(7, "0x" + "e" * 64) == "0x" + "d" * 64
    assert c.complete(7, "0x" + "f" * 64) == "0x" + "d" * 64
    sent = [x for x in handler.captured if x["method"] == "eth_sendRawTransaction"]  # type: ignore[attr-defined]
    assert len(sent) == 6 and all(s["params"][0].startswith("0x") for s in sent)


# --- factory gating ---------------------------------------------------------


def test_build_erc8183_disabled_by_default() -> None:
    assert build_erc8183(Settings(erc8183_enabled=False)) is None


def test_build_erc8183_enabled_reads_only_without_key() -> None:
    c = build_erc8183(Settings(erc8183_enabled=True, rpc_url="http://rpc.local"))
    assert isinstance(c, Erc8183Client) and not c.can_write
    c.close()


def test_build_erc8183_enabled_with_key_can_write() -> None:
    c = build_erc8183(
        Settings(erc8183_enabled=True, rpc_url="http://rpc.local", agent_private_key=TEST_KEY)
    )
    assert c is not None and c.can_write
    c.close()
