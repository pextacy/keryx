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
# recibo's metadata carries an `encrypt` scheme: "none" (plaintext) vs "pgp" (encrypted, only
# the parties can read). We model the visibility distinction without real PGP: a CONFIDENTIAL
# memo's note is redacted in the public feed (/memos) but returned in full on a direct read
# (/memo/{tx}) — the on-chain analogue is a recibo PGP memo only the counterparties decrypt.
SCHEME_PLAINTEXT = "plaintext"
SCHEME_CONFIDENTIAL = "confidential"
# IANA media type recibo stamps on a plaintext message.
DEFAULT_MIME = "text/plain;charset=UTF-8"
_REDACTED = "🔒 confidential"

# What a payment was for. A small taxonomy so a receipt feed is filterable/legible.
MEMO_KINDS = (
    "citation",
    "invoice",
    "attestation",
    "authorization",  # recibo ERC-3009 transferWithAuthorization — paid by off-chain signature
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
    mime: str = DEFAULT_MIME
    in_reply_to: str = ""  # tx hash of the memo this one replies to (recibo response thread)
    attachment_url: str = ""  # link to a non-text payload (recibo carries mime'd attachments)

    @property
    def confidential(self) -> bool:
        return self.scheme == SCHEME_CONFIDENTIAL

    def line(self) -> str:
        """A one-line plaintext rendering (the legacy memo string, kept for back-compat).

        A confidential memo redacts its note here (this string can surface in public feeds);
        kind + ref stay visible so the receipt is still legible.
        """
        note = _REDACTED if self.confidential else self.note
        head = self.kind if self.kind != "note" else ""
        parts = [p for p in (head, self.ref, note) if p]
        return ": ".join(parts) if parts else note

    def as_dict(self, *, public: bool = False) -> dict[str, object]:
        """Serialise the envelope. ``public=True`` redacts a confidential memo's note (for the
        /memos feed); a direct read passes ``public=False`` to return the full note."""
        note = _REDACTED if (public and self.confidential) else self.note
        return {
            "kind": self.kind,
            "ref": self.ref,
            "note": note,
            "message_from": self.message_from,
            "message_to": self.message_to,
            "version": self.version,
            "scheme": self.scheme,
            "mime": self.mime,
            "in_reply_to": self.in_reply_to,
            "attachment_url": self.attachment_url,
        }


def build_memo(
    *,
    kind: str = "note",
    ref: str = "",
    note: str = "",
    message_from: str = "",
    message_to: str = "",
    confidential: bool = False,
    in_reply_to: str = "",
    attachment_url: str = "",
    mime: str = DEFAULT_MIME,
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
        scheme=SCHEME_CONFIDENTIAL if confidential else SCHEME_PLAINTEXT,
        mime=mime,
        in_reply_to=in_reply_to.strip(),
        attachment_url=attachment_url.strip(),
    )
