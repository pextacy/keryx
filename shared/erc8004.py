"""ERC-8004 agent identity + reputation on Arc Testnet.

Gives Keryx's paying agent a verifiable on-chain identity (IdentityRegistry) and lets the
verifier record an author/agent's grounding quality as on-chain reputation
(ReputationRegistry) — turning the grounding score ``g`` into a portable, auditable
reputation signal. Reads and writes go over Arc JSON-RPC via the shared ``JsonRpcClient``
(no web3); calls are ABI-encoded with ``eth_abi`` and signed with ``eth_account`` (same key
the agent signs attestations with). Contract addresses are config (verified vs docs.arc.io).

Opt-in and resilient: reads need an RPC url; writes need ``KERYX_AGENT_PRIVATE_KEY``. With
neither configured this module is never constructed and nothing touches the network — the
offline default is unaffected. Per ERC-8004, an agent's owner cannot rate its own agent, so
Keryx records reputation as an external verifier.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode
from eth_account import Account
from eth_utils import keccak, to_checksum_address

from shared.chain import JsonRpcClient

log = logging.getLogger("keryx.erc8004")

# ERC-721 Transfer(from, to, tokenId) — tokenId is the 3rd INDEXED arg (topics[3]).
_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
# Arc RPC caps eth_getLogs at ~10,000 blocks per query (docs.arc.io ERC-8004 quickstart).
GETLOGS_MAX_BLOCKS = 10_000


def selector(signature: str) -> bytes:
    """4-byte function selector for a Solidity signature, e.g. ``register(string)``."""
    return keccak(text=signature)[:4]


def _calldata(signature: str, arg_types: list[str], args: list[object]) -> str:
    return "0x" + (selector(signature) + abi_encode(arg_types, args)).hex()


def _topic_address(addr: str) -> str:
    return "0x" + addr[2:].lower().rjust(64, "0")


def feedback_score(g: float) -> int:
    """Map a grounding score g in [0,1] to an ERC-8004 reputation score (int128 0..100)."""
    return max(0, min(100, round(100 * g)))


def _to_bytes32(value: str | bytes) -> bytes:
    """Normalize a 0x-hex string or bytes to a 32-byte value (right-padded).

    Validates at the system boundary: a value longer than 32 bytes is rejected.
    """
    if isinstance(value, str):
        try:
            raw = bytes.fromhex(value[2:] if value.startswith("0x") else value)
        except ValueError as exc:
            raise ValueError(f"invalid hash hex: {value!r}") from exc
    else:
        raw = value
    if len(raw) > 32:
        raise ValueError("request_hash must be <=32 bytes")
    return raw.ljust(32, b"\x00")


@dataclass(frozen=True)
class AgentIdentity:
    agent_id: int
    owner: str
    metadata_uri: str


@dataclass(frozen=True)
class ValidationStatus:
    """On-chain ERC-8004 ValidationRegistry status for a request (100=passed, 0=failed)."""

    validator: str
    agent_id: int
    response: int
    tag: str
    last_update: int

    @property
    def passed(self) -> bool:
        """True when the validator recorded a passing response (100)."""
        return self.response == 100


class Erc8004Client:
    """Read agent identity and write reputation/identity txs on Arc's ERC-8004 registries."""

    def __init__(
        self,
        rpc: JsonRpcClient,
        *,
        identity_registry: str,
        reputation_registry: str,
        validation_registry: str,
        chain_id: int,
        private_key: str | None = None,
        gas_limit: int = 300_000,
    ) -> None:
        self._rpc = rpc
        self.identity_registry = to_checksum_address(identity_registry)
        self.reputation_registry = to_checksum_address(reputation_registry)
        self.validation_registry = to_checksum_address(validation_registry)
        self.chain_id = chain_id
        self.gas_limit = gas_limit
        # Writes require a key; reads work without one. Account is the agent's signing key.
        self._account = Account.from_key(private_key) if private_key else None
        # Serialise writes: the nonce read -> sign -> broadcast must be atomic, else two
        # concurrent writes fetch the same "pending" nonce and one tx is dropped/replaced.
        self._send_lock = threading.Lock()

    @property
    def can_write(self) -> bool:
        return self._account is not None

    def close(self) -> None:
        self._rpc.close()

    # --- reads ---------------------------------------------------------------

    def _eth_call(self, to: str, signature: str, arg_types: list[str], args: list[object]) -> bytes:
        data = _calldata(signature, arg_types, args)
        result = self._rpc.call("eth_call", [{"to": to, "data": data}, "latest"])
        return (
            bytes.fromhex(result[2:])
            if isinstance(result, str) and result.startswith("0x")
            else b""
        )

    def agent_id_of(self, owner: str, *, from_block: int | None = None) -> int | None:
        """Resolve an owner's agent id from the IdentityRegistry mint (Transfer) log.

        Bounded to the last ``GETLOGS_MAX_BLOCKS`` blocks (Arc's eth_getLogs cap) unless an
        explicit ``from_block`` is given. Returns the most recent token id, or None.
        """
        if from_block is None:
            latest = int(self._rpc.call("eth_blockNumber", []), 16)
            from_block = max(0, latest - GETLOGS_MAX_BLOCKS)
        logs = self._rpc.call(
            "eth_getLogs",
            [
                {
                    "address": self.identity_registry,
                    "topics": [_TRANSFER_TOPIC, None, _topic_address(owner)],
                    "fromBlock": hex(from_block),
                    "toBlock": "latest",
                }
            ],
        )
        if not isinstance(logs, list) or not logs:
            return None
        last = logs[-1]
        topics = last.get("topics") or []
        return int(topics[3], 16) if len(topics) >= 4 else None

    def owner_of(self, agent_id: int) -> str:
        raw = self._eth_call(self.identity_registry, "ownerOf(uint256)", ["uint256"], [agent_id])
        return to_checksum_address(abi_decode(["address"], raw)[0]) if raw else ""

    def token_uri(self, agent_id: int) -> str:
        raw = self._eth_call(self.identity_registry, "tokenURI(uint256)", ["uint256"], [agent_id])
        return str(abi_decode(["string"], raw)[0]) if raw else ""

    def identity(self, owner: str) -> AgentIdentity | None:
        """Full identity for an owner wallet, or None if it has not registered."""
        agent_id = self.agent_id_of(owner)
        if agent_id is None:
            return None
        return AgentIdentity(agent_id, self.owner_of(agent_id), self.token_uri(agent_id))

    def validation_status(self, request_hash: str | bytes) -> ValidationStatus | None:
        """Read the ValidationRegistry status for ``request_hash``, or None if unset.

        A zero-address validator (no validation recorded) and an empty RPC return both
        degrade to None. Decodes all 6 return values, discarding the responseHash (index 3).
        """
        raw = self._eth_call(
            self.validation_registry,
            "getValidationStatus(bytes32)",
            ["bytes32"],
            [_to_bytes32(request_hash)],
        )
        if not raw:
            return None
        decoded = abi_decode(["address", "uint256", "uint8", "bytes32", "string", "uint256"], raw)
        validator = str(decoded[0])
        if int(validator, 16) == 0:
            return None
        return ValidationStatus(
            validator=to_checksum_address(validator),
            agent_id=int(decoded[1]),
            response=int(decoded[2]),
            tag=str(decoded[4]),
            last_update=int(decoded[5]),
        )

    # --- writes (require a signing key) --------------------------------------

    def _send(self, to: str, signature: str, arg_types: list[str], args: list[object]) -> str:
        if self._account is None:
            raise RuntimeError("ERC-8004 write requires KERYX_AGENT_PRIVATE_KEY")
        sender = self._account.address
        with self._send_lock:
            nonce = int(self._rpc.call("eth_getTransactionCount", [sender, "pending"]), 16)
            gas_price = int(self._rpc.call("eth_gasPrice", []), 16)
            tx = {
                "to": to_checksum_address(to),
                "data": _calldata(signature, arg_types, args),
                "value": 0,
                "nonce": nonce,
                "gas": self.gas_limit,
                "gasPrice": gas_price,
                "chainId": self.chain_id,
            }
            signed = self._account.sign_transaction(tx)
            raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
            tx_hash = self._rpc.call("eth_sendRawTransaction", ["0x" + raw.hex()])
        return str(tx_hash)

    def register(self, metadata_uri: str) -> str:
        """Register this agent's identity (mints an ERC-721); returns the tx hash."""
        return self._send(self.identity_registry, "register(string)", ["string"], [metadata_uri])

    def give_feedback(
        self, agent_id: int, *, g: float, tag: str = "keryx_grounded_citation"
    ) -> str:
        """Record grounding-derived reputation for ``agent_id`` (score = round(100*g))."""
        feedback_hash = keccak(text=tag)
        return self._send(
            self.reputation_registry,
            "giveFeedback(uint256,int128,uint8,string,string,string,string,bytes32)",
            ["uint256", "int128", "uint8", "string", "string", "string", "string", "bytes32"],
            [agent_id, feedback_score(g), 0, tag, "", "", "", feedback_hash],
        )

    def request_validation(
        self, validator: str, agent_id: int, request_uri: str, request_hash: str | bytes
    ) -> str:
        """Ask ``validator`` to validate ``agent_id``'s grounding claim; returns the tx hash."""
        return self._send(
            self.validation_registry,
            "validationRequest(address,uint256,string,bytes32)",
            ["address", "uint256", "string", "bytes32"],
            [to_checksum_address(validator), agent_id, request_uri, _to_bytes32(request_hash)],
        )

    def respond_validation(
        self,
        request_hash: str | bytes,
        response: int,
        *,
        response_uri: str = "",
        response_hash: str | bytes = b"",
        tag: str = "keryx_grounding",
    ) -> str:
        """Record a validation response (100=passed, 0=failed); returns the tx hash.

        ``response`` is a uint8 — validated to 0..255 at the boundary.
        """
        if not 0 <= response <= 255:
            raise ValueError("response must be a uint8 (0..255)")
        return self._send(
            self.validation_registry,
            "validationResponse(bytes32,uint8,string,bytes32,string)",
            ["bytes32", "uint8", "string", "bytes32", "string"],
            [_to_bytes32(request_hash), response, response_uri, _to_bytes32(response_hash), tag],
        )
