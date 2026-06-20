"""ERC-8183 AgenticCommerce — job escrow on Arc Testnet.

A research/citation job with USDC escrow: a client creates a job for the Keryx agent
(provider), funds escrow, the agent submits a deliverable hash, and the evaluator
completes it — releasing escrow to the provider. This generalizes Keryx's pay-per-citation
into pay-per-job, settled on-chain (AgenticCommerce reference impl, docs.arc.io ERC-8183).

Reads/writes go over Arc JSON-RPC via the shared ``JsonRpcClient`` (no web3); calls are
ABI-encoded with ``eth_abi`` and signed with ``eth_account``. Opt-in (KERYX_ERC8183_ENABLED);
writes need a signing key. Offline default is untouched — nothing here runs unconfigured.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from decimal import Decimal

from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode
from eth_account import Account
from eth_utils import keccak, to_checksum_address

from shared.chain import JsonRpcClient

log = logging.getLogger("keryx.erc8183")

_USDC_DECIMALS = 6
_ZERO_ADDRESS = "0x" + "0" * 40
# keccak256("JobCreated(uint256,address,address,address,uint256,address)") — jobId is topics[1].
_JOB_CREATED_TOPIC = (
    "0x" + keccak(text="JobCreated(uint256,address,address,address,uint256,address)").hex()
)
# The full job struct returned by getJob(uint256).
_JOB_TUPLE = "(uint256,address,address,address,string,uint256,uint256,uint8,address)"


class JobStatus(enum.IntEnum):
    OPEN = 0
    FUNDED = 1
    SUBMITTED = 2
    COMPLETED = 3
    REJECTED = 4
    EXPIRED = 5


@dataclass(frozen=True)
class Job:
    """On-chain ERC-8183 job state."""

    id: int
    client: str
    provider: str
    evaluator: str
    description: str
    budget: Decimal  # USDC (6 decimals)
    expired_at: int
    status: JobStatus
    hook: str


def _selector(signature: str) -> bytes:
    return keccak(text=signature)[:4]


def _calldata(signature: str, arg_types: list[str], args: list[object]) -> str:
    return "0x" + (_selector(signature) + abi_encode(arg_types, args)).hex()


def _to_atomic(amount: Decimal) -> int:
    return int((amount * (10**_USDC_DECIMALS)).to_integral_value())


def _to_bytes32(value: str | bytes) -> bytes:
    raw = (
        bytes.fromhex(value[2:] if value.startswith("0x") else value)
        if isinstance(value, str)
        else value
    )
    if len(raw) > 32:
        raise ValueError("value must be <=32 bytes")
    return raw.ljust(32, b"\x00")


class Erc8183Client:
    """Drive the ERC-8183 job lifecycle (create -> fund -> submit -> complete) on Arc."""

    def __init__(
        self,
        rpc: JsonRpcClient,
        *,
        contract: str,
        usdc_address: str,
        chain_id: int,
        private_key: str | None = None,
        gas_limit: int = 400_000,
    ) -> None:
        self._rpc = rpc
        self.contract = to_checksum_address(contract)
        self.usdc_address = to_checksum_address(usdc_address)
        self.chain_id = chain_id
        self.gas_limit = gas_limit
        self._account = Account.from_key(private_key) if private_key else None

    @property
    def can_write(self) -> bool:
        return self._account is not None

    def close(self) -> None:
        self._rpc.close()

    # --- reads ---------------------------------------------------------------

    def get_job(self, job_id: int) -> Job | None:
        """Read job state, or None if the RPC returns nothing."""
        data = _calldata("getJob(uint256)", ["uint256"], [job_id])
        result = self._rpc.call("eth_call", [{"to": self.contract, "data": data}, "latest"])
        if not (isinstance(result, str) and result.startswith("0x") and len(result) > 2):
            return None
        (job,) = abi_decode([_JOB_TUPLE], bytes.fromhex(result[2:]))
        return Job(
            id=int(job[0]),
            client=to_checksum_address(job[1]),
            provider=to_checksum_address(job[2]),
            evaluator=to_checksum_address(job[3]),
            description=str(job[4]),
            budget=Decimal(int(job[5])) / Decimal(10**_USDC_DECIMALS),
            expired_at=int(job[6]),
            status=JobStatus(int(job[7])),
            hook=to_checksum_address(job[8]),
        )

    def job_id_from_receipt(self, tx_hash: str) -> int | None:
        """Extract the jobId from the JobCreated event in a createJob receipt."""
        receipt = self._rpc.call("eth_getTransactionReceipt", [tx_hash])
        if not isinstance(receipt, dict):
            return None
        for entry in receipt.get("logs") or []:
            topics = entry.get("topics") or []
            if (
                str(entry.get("address", "")).lower() == self.contract.lower()
                and len(topics) >= 2
                and str(topics[0]).lower() == _JOB_CREATED_TOPIC
            ):
                return int(topics[1], 16)
        return None

    # --- writes (require a signing key) --------------------------------------

    def _send(self, to: str, signature: str, arg_types: list[str], args: list[object]) -> str:
        if self._account is None:
            raise RuntimeError("ERC-8183 write requires a signing key")
        sender = self._account.address
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
        return str(self._rpc.call("eth_sendRawTransaction", ["0x" + raw.hex()]))

    def create_job(
        self,
        provider: str,
        evaluator: str,
        expired_at: int,
        description: str,
        *,
        hook: str = _ZERO_ADDRESS,
    ) -> str:
        return self._send(
            self.contract,
            "createJob(address,address,uint256,string,address)",
            ["address", "address", "uint256", "string", "address"],
            [
                to_checksum_address(provider),
                to_checksum_address(evaluator),
                expired_at,
                description,
                to_checksum_address(hook),
            ],
        )

    def set_budget(self, job_id: int, budget: Decimal) -> str:
        return self._send(
            self.contract,
            "setBudget(uint256,uint256,bytes)",
            ["uint256", "uint256", "bytes"],
            [job_id, _to_atomic(budget), b""],
        )

    def approve_usdc(self, budget: Decimal) -> str:
        """Approve the job contract to pull ``budget`` USDC before funding escrow."""
        return self._send(
            self.usdc_address,
            "approve(address,uint256)",
            ["address", "uint256"],
            [self.contract, _to_atomic(budget)],
        )

    def fund(self, job_id: int) -> str:
        return self._send(self.contract, "fund(uint256,bytes)", ["uint256", "bytes"], [job_id, b""])

    def submit(self, job_id: int, deliverable_hash: str | bytes) -> str:
        return self._send(
            self.contract,
            "submit(uint256,bytes32,bytes)",
            ["uint256", "bytes32", "bytes"],
            [job_id, _to_bytes32(deliverable_hash), b""],
        )

    def complete(self, job_id: int, reason_hash: str | bytes) -> str:
        return self._send(
            self.contract,
            "complete(uint256,bytes32,bytes)",
            ["uint256", "bytes32", "bytes"],
            [job_id, _to_bytes32(reason_hash), b""],
        )
