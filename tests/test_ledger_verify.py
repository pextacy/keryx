"""annotate_recent — attach on-chain verification + reconciliation to ledger rows."""

from __future__ import annotations

from decimal import Decimal

from agent.ledger_verify import annotate_recent
from shared.chain import ChainVerification

AUTHOR = "0x" + "a" * 40


class _StubReader:
    """Duck-types ChainReader.verify_citation with canned verifications by tx hash."""

    def __init__(self, by_tx: dict[str, ChainVerification]) -> None:
        self._by_tx = by_tx
        self.calls: list[tuple[str, str | None]] = []

    def verify_citation(self, tx_hash: str, *, expected_to: str | None = None) -> ChainVerification:
        self.calls.append((tx_hash, expected_to))
        return self._by_tx[tx_hash]


def _row(tx: str | None, author: str | None = AUTHOR) -> dict[str, object]:
    return {
        "source_url": "https://a.com",
        "author_wallet": author,
        "tx_hash": tx,
        "amount": "0.004",
    }


def test_annotates_confirmed_and_reconciles() -> None:
    reader = _StubReader(
        {
            "0xok": ChainVerification(
                "0xok", True, to=AUTHOR, amount=Decimal("0.004"), reason="ok"
            ),
            "0xbad": ChainVerification("0xbad", False, reason="reverted"),
        }
    )
    out = annotate_recent(reader, [_row("0xok"), _row("0xbad")])  # type: ignore[arg-type]
    entries = out["entries"]
    assert entries[0]["chain_verified"] is True and entries[0]["on_chain_amount"] == "0.004"
    assert entries[1]["chain_verified"] is False and entries[1]["chain_reason"] == "reverted"
    assert out["verified_count"] == 1 and out["reconciled_usdc"] == "0.004"
    # expected recipient is threaded into the verification call.
    assert reader.calls[0] == ("0xok", AUTHOR)


def test_row_without_tx_is_marked_unverified_without_calling_reader() -> None:
    reader = _StubReader({})
    out = annotate_recent(reader, [_row(None)])  # type: ignore[arg-type]
    assert out["entries"][0]["chain_verified"] is False
    assert out["entries"][0]["chain_reason"] == "no_tx"
    assert reader.calls == []  # no tx -> no RPC
