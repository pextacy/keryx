"""Circle Developer-Controlled Wallets — programmatic wallet provisioning on Arc.

A thin REST client (httpx, no heavy SDK) for Circle's W3S developer wallets API
(developers.circle.com). Keryx uses it to provision Arc agent/author wallets and execute
contract calls (e.g. ERC-8004 register / ERC-8183 job lifecycle) with Gas Station
sponsorship — without holding raw private keys.

Opt-in: a client is built only when ``KERYX_CIRCLE_API_KEY`` is set; offline default never
touches the network. Pooled client, explicit timeout, bounded retry on transient errors.

NOTE: Circle's write calls require an ``entitySecretCiphertext`` — a per-request RSA-OAEP
encryption of your registered Entity Secret against Circle's public key. Generating it needs
Circle's tooling/SDK; this client takes the ciphertext as an argument so it stays
dependency-light and faithful. Reads (transaction status) need only the API key.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

import httpx

log = logging.getLogger("keryx.circle_wallets")

_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
ARC_TESTNET = "ARC-TESTNET"


class CircleWalletsError(RuntimeError):
    """A Circle API call failed (non-2xx after retries, or a failed transaction)."""


class CircleWalletsClient:
    """REST client for Circle's Developer-Controlled Wallets (W3S) API."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.circle.com",
        timeout: float = 15.0,
        max_retries: int = 2,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )
        self._sleep: Callable[[float], None] = time.sleep  # injectable in tests

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            try:
                self._client.close()
            except Exception as exc:  # noqa: BLE001 — close must never raise
                log.warning("CircleWalletsClient close failed: %s", exc)
            self._owns_client = False

    # --- HTTP ----------------------------------------------------------------

    def _request(self, method: str, path: str, *, body: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._client.request(method, url, json=body, headers=headers)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in _RETRYABLE_STATUS:
                    raise CircleWalletsError(
                        f"Circle API {exc.response.status_code}: {exc.response.text[:200]}"
                    ) from exc
                last_exc = exc
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
            if attempt < self.max_retries:
                self._sleep(min(0.2 * (2**attempt), 2.0))
        raise CircleWalletsError(f"Circle API unreachable: {last_exc}")

    @staticmethod
    def _idempotency_key(given: str | None) -> str:
        return given or str(uuid.uuid4())

    # --- wallets -------------------------------------------------------------

    def create_wallet_set(
        self, name: str, *, entity_secret_ciphertext: str, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        body = {
            "idempotencyKey": self._idempotency_key(idempotency_key),
            "entitySecretCiphertext": entity_secret_ciphertext,
            "name": name,
        }
        data = self._request("POST", "/v1/w3s/developer/walletSets", body=body)
        result: dict[str, Any] = data.get("data", {}).get("walletSet", {})
        return result

    def create_wallets(
        self,
        wallet_set_id: str,
        *,
        entity_secret_ciphertext: str,
        count: int = 1,
        blockchains: tuple[str, ...] = (ARC_TESTNET,),
        account_type: str = "SCA",
        idempotency_key: str | None = None,
    ) -> list[dict[str, Any]]:
        body = {
            "idempotencyKey": self._idempotency_key(idempotency_key),
            "entitySecretCiphertext": entity_secret_ciphertext,
            "walletSetId": wallet_set_id,
            "blockchains": list(blockchains),
            "count": count,
            "accountType": account_type,
        }
        data = self._request("POST", "/v1/w3s/developer/wallets", body=body)
        wallets: list[dict[str, Any]] = data.get("data", {}).get("wallets", [])
        return wallets

    def create_contract_execution(
        self,
        *,
        wallet_id: str,
        contract_address: str,
        abi_function_signature: str,
        abi_parameters: list[Any],
        entity_secret_ciphertext: str,
        fee_level: str = "MEDIUM",
        idempotency_key: str | None = None,
    ) -> str:
        """Execute a contract call from a Circle wallet; returns the transaction id."""
        body = {
            "idempotencyKey": self._idempotency_key(idempotency_key),
            "entitySecretCiphertext": entity_secret_ciphertext,
            "walletId": wallet_id,
            "contractAddress": contract_address,
            "abiFunctionSignature": abi_function_signature,
            "abiParameters": abi_parameters,
            "feeLevel": fee_level,
        }
        data = self._request("POST", "/v1/w3s/developer/transactions/contractExecution", body=body)
        return str(data.get("data", {}).get("id", ""))

    # --- transactions --------------------------------------------------------

    def get_transaction(self, tx_id: str) -> dict[str, Any]:
        data = self._request("GET", f"/v1/w3s/transactions/{tx_id}")
        tx: dict[str, Any] = data.get("data", {}).get("transaction", {})
        return tx

    def wait_for_transaction(self, tx_id: str, *, attempts: int = 30, interval: float = 2.0) -> str:
        """Poll until the transaction is COMPLETE (returns its tx hash) or FAILED/timeout."""
        for _ in range(attempts):
            tx = self.get_transaction(tx_id)
            state = tx.get("state")
            if state == "COMPLETE":
                return str(tx.get("txHash", ""))
            if state == "FAILED":
                raise CircleWalletsError(f"transaction {tx_id} failed on-chain")
            self._sleep(interval)
        raise CircleWalletsError(f"transaction {tx_id} timed out")
