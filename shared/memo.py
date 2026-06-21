"""Structured payment memos — provenance that travels with a settlement.

Ports the shape of circlefin/recibo (encrypted memos for ERC-20 transfers): a memo there
is metadata (a version + encryption scheme) plus a message, routed messageFrom -> messageTo.
Recibo encrypts the message (PGP) for invoicing / ISO20022 / Travel-Rule use; Keryx ships the
plaintext scheme — the same envelope, minus the crypto — so a payment says *why* it was made:
a citation URL, an attestation hash, a job id.

This is offline and storage-agnostic: the agent keeps these records in-memory keyed by tx hash
and exposes them via GET /memo/{tx} and GET /memos (a recibo-style receipt feed).
"""

from __future__ import annotations

from dataclasses import dataclass

# Recibo metadata: a version + an encryption scheme byte. We support only the plaintext scheme
# (the agent settles test USDC offline); recibo's PGP scheme is the on-chain encrypted variant.
RECIBO_VERSION = 1
SCHEME_PLAINTEXT = "plaintext"

# What a payment was for. A small taxonomy so a receipt feed is filterable/legible.
MEMO_KINDS = (
    "citation",
    "invoice",
    "attestation",
    "job",
    "payout",
    "royalty",
    "swap",
    "refund",
    "note",
    "other",
)


@dataclass(frozen=True)
class Memo:
    """A structured provenance memo (recibo envelope: metadata + message + routing)."""

    kind: str
    ref: str  # the referenced thing: URL, attestation hash, job id (may be empty)
    note: str  # free-text message
    message_from: str  # who paid (agent/sender)
    message_to: str  # who was paid
    version: int = RECIBO_VERSION
    scheme: str = SCHEME_PLAINTEXT

    def line(self) -> str:
        """A one-line plaintext rendering (the legacy memo string, kept for back-compat)."""
        head = self.kind if self.kind != "note" else ""
        parts = [p for p in (head, self.ref, self.note) if p]
        return ": ".join(parts) if parts else self.note

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "ref": self.ref,
            "note": self.note,
            "message_from": self.message_from,
            "message_to": self.message_to,
            "version": self.version,
            "scheme": self.scheme,
        }


def build_memo(
    *,
    kind: str = "note",
    ref: str = "",
    note: str = "",
    message_from: str = "",
    message_to: str = "",
) -> Memo:
    """Build a Memo, normalising the kind to the known taxonomy (unknown -> 'other')."""
    k = kind.strip().lower()
    if k not in MEMO_KINDS:
        k = "other"
    return Memo(
        kind=k,
        ref=ref.strip(),
        note=note.strip(),
        message_from=message_from,
        message_to=message_to,
    )
