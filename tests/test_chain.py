"""ChainReader — JSON-RPC receipt verification + ERC-20 Transfer decode. No network."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from shared.chain import ChainReader, _addr_from_topic, _to_usdc

USDC = "0x3600000000000000000000000000000000000000"
AUTHOR = "0x" + "a" * 40
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _topic_addr(addr: str) -> str:
    return "0x" + "0" * 24 + addr[2:]


def _receipt(
    *, status: str = "0x1", to: str = AUTHOR, value: int = 4000, addr: str = USDC
) -> dict[str, Any]:
    return {
        "status": status,
        "blockNumber": "0x10",
        "logs": [
            {
                "address": addr,
                "topics": [TRANSFER, _topic_addr("0x" + "0" * 40), _topic_addr(to)],
                "data": hex(value),
            }
        ],
    }


def _reader(handler: Any, **kw: Any) -> ChainReader:
    r = ChainReader(
        "http://rpc.local", USDC, client=httpx.Client(transport=httpx.MockTransport(handler)), **kw
    )
    r._sleep = lambda _s: None
    return r


def _envelope(result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": 1, "result": result}


def test_decode_helpers() -> None:
    assert _addr_from_topic(_topic_addr(AUTHOR)) == AUTHOR
    assert _to_usdc(hex(4000)) == Decimal("0.004")


def test_verify_confirmed_reads_amount_and_recipient() -> None:
    r = _reader(lambda req: httpx.Response(200, json=_envelope(_receipt())))
    v = r.verify_citation("0x" + "1" * 64, expected_to=AUTHOR)
    assert v.confirmed and v.to == AUTHOR and v.amount == Decimal("0.004") and v.block == 16


def test_reverted_status_is_unconfirmed() -> None:
    r = _reader(lambda req: httpx.Response(200, json=_envelope(_receipt(status="0x0"))))
    v = r.verify_citation("0xtx")
    assert not v.confirmed and v.reason == "reverted"


def test_missing_tx_is_not_found() -> None:
    r = _reader(lambda req: httpx.Response(200, json=_envelope(None)))
    v = r.verify_citation("0xtx")
    assert not v.confirmed and v.reason == "not_found"


def test_recipient_mismatch_flagged_but_amount_read() -> None:
    r = _reader(lambda req: httpx.Response(200, json=_envelope(_receipt(to=AUTHOR))))
    v = r.verify_citation("0xtx", expected_to="0x" + "b" * 40)
    assert not v.confirmed and v.reason == "recipient_mismatch" and v.amount == Decimal("0.004")


def test_no_usdc_transfer_log() -> None:
    other = "0x" + "9" * 40
    r = _reader(lambda req: httpx.Response(200, json=_envelope(_receipt(addr=other))))
    v = r.verify_citation("0xtx")
    assert not v.confirmed and v.reason == "no_usdc_transfer"


def test_retry_then_succeed() -> None:
    calls = {"n": 0}

    def _h(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json=_envelope(_receipt()))

    r = _reader(_h, max_retries=2)
    assert r.verify_citation("0xtx", expected_to=AUTHOR).confirmed
    assert calls["n"] == 3


def test_rpc_error_degrades_to_unverified() -> None:
    r = _reader(
        lambda req: httpx.Response(
            200, json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "boom"}}
        )
    )
    v = r.verify_citation("0xtx")
    assert not v.confirmed and v.reason.startswith("rpc_error")


def test_block_number_decodes_hex() -> None:
    r = _reader(lambda req: httpx.Response(200, json=_envelope("0x2a")))
    assert r.block_number() == 42
