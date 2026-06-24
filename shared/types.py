"""Frozen wire types shared by the rail and the agent.

These three objects are the contract named in CLAUDE.md / phases.md:

    CitationIntent = { source_id, author_wallet, amount, payment_auth }
    Receipt        = { source_id, tx_hash, status }
    Attestation    = { query_hash, answer_hash, citations[], agent_pubkey, ts }

All models are ``frozen=True`` — the contract is literally immutable at runtime so
neither instance can mutate a shared object mid-flight. Amounts are USDC carried as
``Decimal`` (USDC has 6 on-chain decimals; floor is $0.000001). Never use float for
money.
"""

from __future__ import annotations

import enum
import re
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 6 decimals -> smallest representable USDC unit, the protocol floor.
USDC_DECIMALS = 6
USDC_FLOOR = Decimal("0.000001")

_HEX_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
# A settlement reference is either an on-chain Arc tx hash (0x + 64 hex) OR a Circle
# Gateway transfer id (UUID). Batched x402 settles many tolls in one on-chain mint and
# returns the per-toll Gateway transfer UUID synchronously — that UUID is the canonical
# settlement reference until/unless the recipient withdraws to an on-chain 0x hash.
_TX_HASH = re.compile(
    r"^0x[0-9a-fA-F]{64}$"
    r"|^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class _Frozen(BaseModel):
    """Base for all shared wire types: immutable, strict, extra fields rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class SettlementStatus(enum.StrEnum):
    """Lifecycle of a single citation settlement."""

    PENDING = "pending"
    SETTLED = "settled"
    FAILED = "failed"


class CitationIntent(_Frozen):
    """A request to settle one citation toll to one author.

    Built by the agent once a source clears the grounding gate (g >= T) and handed
    to ``Rail.settle()``. ``payment_auth`` carries the signed EIP-3009 authorization
    the rail verifies before accepting (opaque to the agent; shape owned by the rail).
    """

    source_id: str = Field(min_length=1)
    author_wallet: str = Field(description="0x-prefixed Arc/EVM address of the author")
    amount: Decimal = Field(description="USDC amount, >= protocol floor")
    payment_auth: dict[str, Any] = Field(
        default_factory=dict,
        description="Signed EIP-3009 authorization payload; verified by the rail",
    )

    @field_validator("author_wallet")
    @classmethod
    def _check_wallet(cls, v: str) -> str:
        if not _HEX_ADDRESS.match(v):
            raise ValueError(f"invalid wallet address: {v!r}")
        return v

    @field_validator("amount")
    @classmethod
    def _check_amount(cls, v: Decimal) -> Decimal:
        if v < USDC_FLOOR:
            raise ValueError(f"amount {v} below USDC floor {USDC_FLOOR}")
        quant = v.quantize(Decimal(1).scaleb(-USDC_DECIMALS))
        if quant != v:
            raise ValueError(f"amount {v} exceeds {USDC_DECIMALS}-decimal USDC precision")
        return v


class Receipt(_Frozen):
    """Result of settling one ``CitationIntent``.

    Returned by ``Rail.settle()``. ``tx_hash`` is the on-chain settlement reference
    (None while pending or on failure). Chain is canonical — this is the rail's word
    on what cleared.
    """

    source_id: str = Field(min_length=1)
    tx_hash: str | None = Field(
        default=None, description="settlement ref: 0x Arc tx hash or Gateway transfer id"
    )
    status: SettlementStatus = SettlementStatus.PENDING

    @field_validator("tx_hash")
    @classmethod
    def _check_tx(cls, v: str | None) -> str | None:
        if v is not None and not _TX_HASH.match(v):
            raise ValueError(f"invalid tx hash: {v!r}")
        return v


class CitationRecord(_Frozen):
    """One line of an attestation: a source the answer was grounded in.

    Per prd.md §6: ``{source_url, g, amount, tx_hash}``. Sources that were evaluated
    but did not clear the gate are recorded separately (amount 0, no tx) so the
    "evaluated-but-not-cited" gating is visible and auditable.
    """

    source_url: str = Field(min_length=1)
    g: float = Field(ge=0.0, le=1.0, description="Grounding score in [0,1]")
    amount: Decimal = Field(ge=Decimal(0), description="USDC paid for this citation")
    tx_hash: str | None = Field(default=None)
    cited: bool = Field(default=True, description="False = evaluated-but-not-cited ($0)")

    @field_validator("tx_hash")
    @classmethod
    def _check_tx(cls, v: str | None) -> str | None:
        if v is not None and not _TX_HASH.match(v):
            raise ValueError(f"invalid tx hash: {v!r}")
        return v


class Attestation(_Frozen):
    """Signed audit trail mapping an answer to the sources that grounded it.

    The centerpiece of the innovation story (prd.md §6): verifiable citation. The
    signature covers the canonical serialization of every field except ``signature``
    itself; ``agent_pubkey`` is the key it verifies against.
    """

    query_hash: str = Field(min_length=1)
    answer_hash: str = Field(min_length=1)
    citations: tuple[CitationRecord, ...] = Field(default_factory=tuple)
    agent_pubkey: str = Field(min_length=1)
    ts: int = Field(description="Unix epoch seconds when the attestation was signed")
    signature: str | None = Field(
        default=None, description="Signature over the canonical payload; set by the signer"
    )
