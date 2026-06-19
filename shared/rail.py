"""The rail interface — frozen contract + a mock implementation.

CC-B (agent) builds against ``MockRail`` until Phase 3 (M2), then swaps in CC-A's
real ``settle()`` with no type changes. The signature is the one fixed in CLAUDE.md:

    settle(intents: list[CitationIntent]) -> list[Receipt]

Returns one Receipt per intent, in the same order.
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

from shared.types import CitationIntent, Receipt, SettlementStatus


@runtime_checkable
class Rail(Protocol):
    """Anything that can settle citation intents on-chain.

    CC-A's production rail and the ``MockRail`` below both satisfy this. The agent
    depends only on this Protocol so the real rail drops in transparently at M2.
    """

    def settle(self, intents: list[CitationIntent]) -> list[Receipt]:
        """Settle a batch of citation tolls; one Receipt per intent, in order."""
        ...


class MockRail:
    """Deterministic fake rail for the agent workstream (Phase 0 -> Phase 3).

    Produces stable, well-formed fake receipts so CC-B is never blocked by the real
    rail. tx hashes are deterministic over (source_id, author_wallet, amount) so tests
    are reproducible. NOT a real settlement — never used past M2.
    """

    def __init__(self, *, fail_source_ids: set[str] | None = None) -> None:
        # Lets tests exercise the failed-settlement path deterministically.
        self._fail = fail_source_ids or set()

    def settle(self, intents: list[CitationIntent]) -> list[Receipt]:
        receipts: list[Receipt] = []
        for intent in intents:
            if intent.source_id in self._fail:
                receipts.append(
                    Receipt(
                        source_id=intent.source_id, tx_hash=None, status=SettlementStatus.FAILED
                    )
                )
                continue
            seed = f"{intent.source_id}|{intent.author_wallet}|{intent.amount}".encode()
            tx_hash = "0x" + hashlib.sha256(seed).hexdigest()
            receipts.append(
                Receipt(
                    source_id=intent.source_id,
                    tx_hash=tx_hash,
                    status=SettlementStatus.SETTLED,
                )
            )
        return receipts
