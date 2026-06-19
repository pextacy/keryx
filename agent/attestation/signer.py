"""Attestation signer/verifier — verifiable citation (ORIGINAL WORK).

prd.md §6: the signed object `{query_hash, answer_hash, citations[], agent_pubkey, ts}`
is the audit trail behind every payment. We sign the canonical serialization with the
agent's secp256k1 key (EIP-191 personal_sign via eth-account); anyone can recover the
signer and verify it matches `agent_pubkey` — "don't trust our DB, verify the signature
and the chain".
"""

from __future__ import annotations

import hashlib
import json
import time
from decimal import Decimal

from eth_account import Account
from eth_account.messages import encode_defunct

from shared.types import Attestation, CitationRecord


def sha256_hex(text: str) -> str:
    return "0x" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_payload(att: Attestation) -> str:
    """Deterministic JSON over every field except the signature. Order-stable."""
    body = {
        "query_hash": att.query_hash,
        "answer_hash": att.answer_hash,
        "citations": [
            {
                "source_url": c.source_url,
                "g": c.g,
                "amount": str(c.amount),
                "tx_hash": c.tx_hash,
                "cited": c.cited,
            }
            for c in att.citations
        ],
        "agent_pubkey": att.agent_pubkey,
        "ts": att.ts,
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


class AttestationSigner:
    """Builds and signs attestations with the agent's key."""

    def __init__(self, private_key: str) -> None:
        if not private_key:
            raise ValueError("agent_private_key required to sign attestations")
        self._acct = Account.from_key(private_key)

    @property
    def address(self) -> str:
        return str(self._acct.address)

    def build(
        self,
        *,
        query: str,
        answer: str,
        citations: list[CitationRecord],
        ts: int | None = None,
    ) -> Attestation:
        unsigned = Attestation(
            query_hash=sha256_hex(query),
            answer_hash=sha256_hex(answer),
            citations=tuple(citations),
            agent_pubkey=self.address,
            ts=ts if ts is not None else int(time.time()),
        )
        payload = _canonical_payload(unsigned)
        signed = self._acct.sign_message(encode_defunct(text=payload))
        # Re-emit frozen, now carrying the signature.
        return unsigned.model_copy(update={"signature": signed.signature.hex()})


def verify_attestation(att: Attestation) -> bool:
    """True iff the signature recovers to ``agent_pubkey`` over the canonical payload."""
    if not att.signature:
        return False
    payload = _canonical_payload(att)
    sig = att.signature if att.signature.startswith("0x") else "0x" + att.signature
    try:
        recovered = Account.recover_message(encode_defunct(text=payload), signature=sig)
    except Exception:
        return False
    return bool(recovered.lower() == att.agent_pubkey.lower())


def amount_decimal(records: list[CitationRecord]) -> Decimal:
    """Total settled across cited records — the per-answer settlement sum."""
    return sum((r.amount for r in records if r.cited), start=Decimal(0))
