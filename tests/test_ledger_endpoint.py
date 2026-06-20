"""GET /ledger — offline default returns the mirror with chain_verified=False, no RPC.

The chain-verified ON path is unit-tested in test_ledger_verify/test_chain; here we lock the
default behavior (no KERYX_LEDGER_VERIFY_CHAIN) so the dashboard works with zero network.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import agent.main as main
from agent.factory import build_chain_reader
from shared.config import Settings


def test_ledger_endpoint_offline_is_mirror() -> None:
    assert main._chain_reader is None  # default settings -> no chain reader built
    client = TestClient(main.app)
    body = client.get("/ledger").json()
    assert body["chain_verified"] is False
    assert "metrics" in body and "recent" in body
    assert "verification" not in body


def test_build_chain_reader_off_by_default() -> None:
    assert build_chain_reader(Settings(ledger_verify_chain=False)) is None


def test_build_chain_reader_on_when_enabled() -> None:
    reader = build_chain_reader(Settings(ledger_verify_chain=True, rpc_url="http://rpc.local"))
    assert reader is not None
    reader.close()
