"""Annotate ledger rows with on-chain verification — the "here's the chain" layer.

Given the ledger's ``recent()`` rows (the DB/in-memory mirror), confirm each citation tx
against chain and attach the on-chain amount/recipient. Bounded to the supplied window so
it never blocks the hot /ask path. Reconciles mirror vs chain for the dashboard.
"""

from __future__ import annotations

from decimal import Decimal

from shared.chain import ChainReader


def annotate_recent(reader: ChainReader, rows: list[dict[str, object]]) -> dict[str, object]:
    """Return chain-annotated rows + a reconciliation summary (chain is canonical)."""
    entries: list[dict[str, object]] = []
    reconciled = Decimal(0)
    verified = 0
    for row in rows:
        tx = row.get("tx_hash")
        author = row.get("author_wallet")
        ann = dict(row)
        if not isinstance(tx, str):
            ann.update(chain_verified=False, on_chain_amount=None, chain_reason="no_tx")
            entries.append(ann)
            continue
        v = reader.verify_citation(tx, expected_to=author if isinstance(author, str) else None)
        ann["chain_verified"] = v.confirmed
        ann["on_chain_amount"] = str(v.amount) if v.amount is not None else None
        ann["chain_reason"] = v.reason
        if v.confirmed and v.amount is not None:
            reconciled += v.amount
            verified += 1
        entries.append(ann)
    return {
        "entries": entries,
        "verified_count": verified,
        "reconciled_usdc": str(reconciled),
        "source": "chain",
    }
