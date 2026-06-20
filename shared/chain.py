"""Chain reads for a verifiable ledger — "don't trust our DB, here's the chain".

Reads Arc via JSON-RPC over httpx (NO web3 dependency) to confirm that a citation's
tx hash actually settled on-chain and to read the on-chain USDC amount/recipient from the
ERC-20 Transfer event. The off-chain ``citations_index`` is a mirror; CHAIN IS CANONICAL
(AGENTS.md #4) — this is how we reconcile against it.

Opt-in: a ``ChainReader`` is built only when ``KERYX_LEDGER_VERIFY_CHAIN`` is true (and an
RPC url is set). Without it, GET /ledger returns today's mirror response and makes ZERO
network calls. Resilience mirrors VoyageEmbedder: one pooled client, explicit timeouts,
bounded retry on transient errors, and graceful degrade — a verification failure yields an
``unverified`` result, never an exception that could break the dashboard.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

log = logging.getLogger("keryx.chain")

# keccak256("Transfer(address,address,uint256)") — the ERC-20 Transfer event topic0.
_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
_USDC_DECIMALS = 6
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class ChainVerification:
    """The on-chain truth for one citation tx (all fields None/False when unverified)."""

    tx_hash: str
    confirmed: bool
    to: str | None = None
    amount: Decimal | None = None
    block: int | None = None
    reason: str = ""


def _addr_from_topic(topic: str) -> str:
    """A 32-byte log topic -> 0x-prefixed 20-byte address (last 40 hex chars)."""
    return "0x" + topic[-40:]


def _to_usdc(value_hex: str) -> Decimal:
    return Decimal(int(value_hex, 16)) / Decimal(10**_USDC_DECIMALS)


class JsonRpcClient:
    """A minimal pooled Arc JSON-RPC client (httpx, no web3) with bounded retry.

    Shared by ``ChainReader`` and the ERC-8004 client (shared/erc8004.py): one pooled
    ``httpx.Client``, explicit timeout, retry on transient transport/5xx errors, raise on a
    permanent error or an RPC ``error`` body. ``close()`` releases the owned client.
    """

    def __init__(
        self,
        rpc_url: str,
        *,
        timeout: float = 8.0,
        max_retries: int = 2,
        backoff_base: float = 0.2,
        backoff_cap: float = 2.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.rpc_url = rpc_url
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )
        self._sleep: Callable[[float], None] = time.sleep  # injectable in tests
        self._id = 0

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            try:
                self._client.close()
            except Exception as exc:  # noqa: BLE001 — close must never raise
                log.warning("JsonRpcClient close failed: %s", exc)
            self._owns_client = False

    def call(self, method: str, params: list[Any]) -> Any:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._client.post(self.rpc_url, json=payload)
                resp.raise_for_status()
                body = resp.json()
                if isinstance(body, dict) and body.get("error"):
                    raise ValueError(f"rpc error: {body['error']}")
                return body.get("result") if isinstance(body, dict) else None
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in _RETRYABLE_STATUS:
                    raise
                last_exc = exc
                self._backoff(attempt)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                self._backoff(attempt)
        assert last_exc is not None
        raise last_exc

    def _backoff(self, attempt: int) -> None:
        if attempt >= self.max_retries:
            return
        self._sleep(min(self.backoff_base * (2**attempt), self.backoff_cap))


class ChainReader:
    """Confirm a settlement tx on Arc and decode its USDC Transfer (recipient + amount)."""

    def __init__(
        self,
        rpc_url: str,
        usdc_address: str,
        *,
        timeout: float = 8.0,
        max_retries: int = 2,
        backoff_base: float = 0.2,
        backoff_cap: float = 2.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.usdc_address = usdc_address.lower()
        self._rpc_client = JsonRpcClient(
            rpc_url,
            timeout=timeout,
            max_retries=max_retries,
            backoff_base=backoff_base,
            backoff_cap=backoff_cap,
            client=client,
        )

    @property
    def rpc_url(self) -> str:
        return self._rpc_client.rpc_url

    @property
    def _sleep(self) -> Callable[[float], None]:
        return self._rpc_client._sleep

    @_sleep.setter
    def _sleep(self, fn: Callable[[float], None]) -> None:
        self._rpc_client._sleep = fn  # keep tests' no-op sleep injection working

    @property
    def max_retries(self) -> int:
        return self._rpc_client.max_retries

    def close(self) -> None:
        self._rpc_client.close()

    def _rpc(self, method: str, params: list[Any]) -> Any:
        return self._rpc_client.call(method, params)

    def block_number(self) -> int:
        return int(self._rpc("eth_blockNumber", []), 16)

    def verify_citation(self, tx_hash: str, *, expected_to: str | None = None) -> ChainVerification:
        """Confirm ``tx_hash`` settled and decode its USDC Transfer (recipient + amount).

        Never raises: any RPC/parse failure returns ``confirmed=False`` with a reason, so a
        flaky RPC degrades the dashboard to "unverified" rather than erroring.
        """
        try:
            receipt = self._rpc("eth_getTransactionReceipt", [tx_hash])
        except Exception as exc:  # noqa: BLE001 — degrade to unverified
            log.warning("verify_citation RPC failed for %s: %s", tx_hash, exc)
            return ChainVerification(tx_hash, False, reason=f"rpc_error: {type(exc).__name__}")

        if not isinstance(receipt, dict):
            return ChainVerification(tx_hash, False, reason="not_found")  # pending/unknown
        if receipt.get("status") not in ("0x1", "0x01"):
            return ChainVerification(tx_hash, False, reason="reverted")

        block = int(receipt["blockNumber"], 16) if receipt.get("blockNumber") else None
        transfer = self._find_transfer(receipt.get("logs") or [])
        if transfer is None:
            return ChainVerification(tx_hash, False, block=block, reason="no_usdc_transfer")
        to, amount = transfer
        if expected_to is not None and to.lower() != expected_to.lower():
            return ChainVerification(
                tx_hash, False, to=to, amount=amount, block=block, reason="recipient_mismatch"
            )
        return ChainVerification(tx_hash, True, to=to, amount=amount, block=block, reason="ok")

    def _find_transfer(self, logs: list[Any]) -> tuple[str, Decimal] | None:
        for entry in logs:
            if not isinstance(entry, dict):
                continue
            topics = entry.get("topics") or []
            if (
                str(entry.get("address", "")).lower() == self.usdc_address
                and len(topics) >= 3
                and str(topics[0]).lower() == _TRANSFER_TOPIC
            ):
                return _addr_from_topic(str(topics[2])), _to_usdc(str(entry.get("data", "0x0")))
        return None
