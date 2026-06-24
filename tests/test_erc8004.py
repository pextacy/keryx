"""ERC-8004 client — ABI calldata, log-based id lookup, signed writes. No network."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from eth_abi import encode as abi_encode
from eth_utils import keccak

from agent.factory import build_erc8004
from shared.chain import JsonRpcClient
from shared.config import Settings
from shared.erc8004 import (
    GETLOGS_MAX_BLOCKS,
    Erc8004Client,
    _to_bytes32,
    feedback_score,
    selector,
)

OWNER = "0x" + "a" * 40
TEST_KEY = "0x" + "1" * 64  # deterministic throwaway signing key (nonzero)
IDENTITY = "0x8004A818BFB912233c491871b3d84c89A494BD9e"
REPUTATION = "0x8004B663056A597Dffe9eCcC1965A193B7388713"
VALIDATION = "0x8004Cb1BF31DAf7788923b405b754f57acEB4272"


def _client(handler: Any, *, key: str | None = None) -> Erc8004Client:
    rpc = JsonRpcClient(
        "http://rpc.local", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    return Erc8004Client(
        rpc,
        identity_registry=IDENTITY,
        reputation_registry=REPUTATION,
        validation_registry=VALIDATION,
        chain_id=0x4CEF52,
        private_key=key,
    )


def _rpc_router(routes: dict[str, Any]) -> Any:
    """A MockTransport handler dispatching on the JSON-RPC method to a canned result."""
    captured: list[dict[str, Any]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured.append(body)
        result = routes.get(body["method"])
        value = result(body["params"]) if callable(result) else result
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": value})

    _handler.captured = captured  # type: ignore[attr-defined]
    return _handler


# --- pure helpers -----------------------------------------------------------


def test_feedback_score_maps_and_clamps() -> None:
    assert feedback_score(0.0) == 0
    assert feedback_score(1.0) == 100
    assert feedback_score(0.5) == 50
    assert feedback_score(0.846) == 85
    assert feedback_score(2.0) == 100 and feedback_score(-1.0) == 0


def test_selector_matches_keccak() -> None:
    assert selector("register(string)") == keccak(text="register(string)")[:4]


# --- reads ------------------------------------------------------------------


def test_agent_id_of_reads_tokenid_from_transfer_log() -> None:
    token_id_topic = "0x" + format(42, "064x")
    handler = _rpc_router(
        {
            "eth_blockNumber": "0x100000",
            "eth_getLogs": [
                {"topics": ["0xddf...", "0x" + "0" * 64, "0x" + "0" * 64, token_id_topic]}
            ],
        }
    )
    assert _client(handler).agent_id_of(OWNER) == 42


def test_agent_id_of_bounds_getlogs_window() -> None:
    handler = _rpc_router({"eth_blockNumber": hex(50_000), "eth_getLogs": []})
    _client(handler).agent_id_of(OWNER)
    getlogs = [c for c in handler.captured if c["method"] == "eth_getLogs"][0]  # type: ignore[attr-defined]
    from_block = int(getlogs["params"][0]["fromBlock"], 16)
    assert from_block == 50_000 - GETLOGS_MAX_BLOCKS


def test_agent_id_of_none_when_no_logs() -> None:
    handler = _rpc_router({"eth_blockNumber": "0x10", "eth_getLogs": []})
    assert _client(handler).agent_id_of(OWNER) is None


def test_owner_of_and_token_uri_decode_eth_call() -> None:
    uri = "ipfs://bafyExample"

    def _eth_call(params: list[Any]) -> str:
        data = params[0]["data"]
        if data.startswith("0x" + selector("ownerOf(uint256)").hex()):
            return "0x" + abi_encode(["address"], [OWNER]).hex()
        return "0x" + abi_encode(["string"], [uri]).hex()

    handler = _rpc_router({"eth_call": _eth_call})
    c = _client(handler)
    assert c.owner_of(42).lower() == OWNER
    assert c.token_uri(42) == uri


def test_identity_composes_id_owner_uri() -> None:
    token_id_topic = "0x" + format(7, "064x")

    def _eth_call(params: list[Any]) -> str:
        data = params[0]["data"]
        if data.startswith("0x" + selector("ownerOf(uint256)").hex()):
            return "0x" + abi_encode(["address"], [OWNER]).hex()
        return "0x" + abi_encode(["string"], ["ipfs://x"]).hex()

    handler = _rpc_router(
        {
            "eth_blockNumber": "0x100",
            "eth_getLogs": [{"topics": ["0xddf", "0x0", "0x0", token_id_topic]}],
            "eth_call": _eth_call,
        }
    )
    ident = _client(handler).identity(OWNER)
    assert ident is not None and ident.agent_id == 7 and ident.metadata_uri == "ipfs://x"


# --- writes -----------------------------------------------------------------


def test_write_without_key_raises() -> None:
    c = _client(_rpc_router({}))
    assert not c.can_write
    with pytest.raises(RuntimeError):
        c.register("ipfs://x")


def test_register_builds_signs_and_sends() -> None:
    handler = _rpc_router(
        {
            "eth_getTransactionCount": "0x1",
            "eth_gasPrice": "0x3b9aca00",
            "eth_sendRawTransaction": "0x" + "d" * 64,
        }
    )
    c = _client(handler, key=TEST_KEY)
    assert c.can_write
    tx = c.register("ipfs://meta")
    assert tx == "0x" + "d" * 64
    sent = [x for x in handler.captured if x["method"] == "eth_sendRawTransaction"][0]  # type: ignore[attr-defined]
    assert sent["params"][0].startswith("0x")  # a signed raw tx was submitted


def test_give_feedback_encodes_score_in_calldata() -> None:
    handler = _rpc_router(
        {
            "eth_getTransactionCount": "0x0",
            "eth_gasPrice": "0x1",
            "eth_sendRawTransaction": "0x" + "e" * 64,
        }
    )
    c = _client(handler, key=TEST_KEY)
    tx = c.give_feedback(99, g=0.9, tag="keryx_grounded_citation")
    assert tx == "0x" + "e" * 64


# --- validation -------------------------------------------------------------


def _validation_call(
    validator: str, agent_id: int, response: int, tag: str, last_update: int
) -> str:
    return (
        "0x"
        + abi_encode(
            ["address", "uint256", "uint8", "bytes32", "string", "uint256"],
            [validator, agent_id, response, b"\x00" * 32, tag, last_update],
        ).hex()
    )


def test_validation_status_decodes_getvalidationstatus() -> None:
    handler = _rpc_router({"eth_call": _validation_call(OWNER, 7, 100, "keryx_grounding", 123)})
    status = _client(handler).validation_status("0x" + format(5, "064x"))
    assert status is not None
    assert status.agent_id == 7
    assert status.response == 100
    assert status.passed is True
    assert status.tag == "keryx_grounding"
    assert status.last_update == 123
    assert status.validator.lower() == OWNER


def test_validation_status_none_on_zero_validator() -> None:
    handler = _rpc_router({"eth_call": _validation_call("0x" + "0" * 40, 0, 0, "", 0)})
    assert _client(handler).validation_status("0x" + format(5, "064x")) is None


def test_validation_status_none_on_empty_return() -> None:
    handler = _rpc_router({"eth_call": "0x"})
    assert _client(handler).validation_status("0x" + format(5, "064x")) is None


def test_request_validation_requires_key() -> None:
    c = _client(_rpc_router({}))
    with pytest.raises(RuntimeError):
        c.request_validation(OWNER, 7, "ipfs://req", "0x" + format(5, "064x"))


def test_request_validation_builds_signs_and_sends() -> None:
    handler = _rpc_router(
        {
            "eth_getTransactionCount": "0x1",
            "eth_gasPrice": "0x3b9aca00",
            "eth_sendRawTransaction": "0x" + "c" * 64,
        }
    )
    c = _client(handler, key=TEST_KEY)
    tx = c.request_validation(OWNER, 7, "ipfs://req", "0x" + format(5, "064x"))
    assert tx == "0x" + "c" * 64
    sent = [x for x in handler.captured if x["method"] == "eth_sendRawTransaction"][0]  # type: ignore[attr-defined]
    assert sent["params"][0].startswith("0x")


def test_respond_validation_encodes_and_sends() -> None:
    handler = _rpc_router(
        {
            "eth_getTransactionCount": "0x0",
            "eth_gasPrice": "0x1",
            "eth_sendRawTransaction": "0x" + "f" * 64,
        }
    )
    c = _client(handler, key=TEST_KEY)
    tx = c.respond_validation("0x" + "0" * 64, 100, tag="keryx_grounding")
    assert tx == "0x" + "f" * 64


def test_respond_validation_rejects_out_of_range() -> None:
    c = _client(_rpc_router({}), key=TEST_KEY)
    with pytest.raises(ValueError):
        c.respond_validation("0x" + "0" * 64, 256)


def test_to_bytes32_rejects_oversized() -> None:
    with pytest.raises(ValueError):
        _to_bytes32("0x" + "a" * 66)


# --- factory gating ---------------------------------------------------------


def test_build_erc8004_disabled_by_default() -> None:
    assert build_erc8004(Settings(erc8004_enabled=False)) is None


def test_build_erc8004_enabled_reads_only_without_key() -> None:
    # agent_private_key="" so the dev .env's signing key can't leak in and flip can_write.
    c = build_erc8004(
        Settings(erc8004_enabled=True, rpc_url="http://rpc.local", agent_private_key="")
    )
    assert isinstance(c, Erc8004Client) and not c.can_write
    c.close()


def test_build_erc8004_enabled_with_key_can_write() -> None:
    c = build_erc8004(
        Settings(erc8004_enabled=True, rpc_url="http://rpc.local", agent_private_key=TEST_KEY)
    )
    assert c is not None and c.can_write
    c.close()
