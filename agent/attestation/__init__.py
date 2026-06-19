"""agent/attestation/ — verifiable citation (ORIGINAL WORK).

Signs/verifies {query_hash, answer_hash, citations[], agent_pubkey, ts} — the audit
trail behind every payment.
"""

from __future__ import annotations

from agent.attestation.signer import (
    AttestationSigner,
    amount_decimal,
    sha256_hex,
    verify_attestation,
)

__all__ = [
    "AttestationSigner",
    "amount_decimal",
    "sha256_hex",
    "verify_attestation",
]
