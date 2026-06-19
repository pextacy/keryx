"""Attestation signer/verifier — sign, verify, tamper-detect."""

from __future__ import annotations

from decimal import Decimal

from eth_account import Account

from agent.attestation import AttestationSigner, sha256_hex, verify_attestation
from shared.types import CitationRecord

KEY = "0x" + "11" * 32


def _records() -> list[CitationRecord]:
    tx = "0x" + "ab" * 32
    return [
        CitationRecord(source_url="https://a", g=0.8, amount=Decimal("0.005"), tx_hash=tx),
        CitationRecord(source_url="https://b", g=0.1, amount=Decimal(0), cited=False),
    ]


def test_sign_and_verify_roundtrip() -> None:
    signer = AttestationSigner(KEY)
    att = signer.build(query="q", answer="a", citations=_records(), ts=1_750_000_000)
    assert att.signature
    assert att.agent_pubkey == signer.address
    assert verify_attestation(att) is True


def test_signer_address_matches_key() -> None:
    signer = AttestationSigner(KEY)
    assert signer.address == Account.from_key(KEY).address


def test_tamper_breaks_verification() -> None:
    signer = AttestationSigner(KEY)
    att = signer.build(query="q", answer="a", citations=_records(), ts=1_750_000_000)
    tampered = att.model_copy(update={"answer_hash": sha256_hex("different")})
    assert verify_attestation(tampered) is False


def test_unsigned_does_not_verify() -> None:
    att = AttestationSigner(KEY).build(query="q", answer="a", citations=[], ts=1)
    unsigned = att.model_copy(update={"signature": None})
    assert verify_attestation(unsigned) is False
