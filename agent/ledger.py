"""Settlement ledger + traction metrics.

A fast read-index of what the agent has settled — the dashboard's data source. Chain
stays canonical (AGENTS.md #4); this mirrors it for speed and is reconciled against
chain when the real rail is live. In-memory now; the Neon ``citations_index`` mirror
swaps in behind the same interface.

Tracks the metrics prd.md §8 leads with: total settled, distinct author wallets paid,
citations settled, distinct sessions, and **team vs external** volume.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol, runtime_checkable

from shared.types import CitationRecord


@runtime_checkable
class LedgerStore(Protocol):
    """The ledger surface main.py depends on — satisfied by ``Ledger`` and ``PgLedger``."""

    def record(
        self,
        *,
        query_hash: str,
        agent_wallet: str,
        citations: list[CitationRecord],
        author_wallets: dict[str, str | None],
        external: bool,
    ) -> None: ...

    def metrics(self) -> dict[str, object]: ...

    def recent(self, limit: int = ...) -> list[dict[str, object]]: ...


@dataclass(frozen=True)
class LedgerEntry:
    query_hash: str
    source_url: str
    author_wallet: str | None
    g: float
    amount: Decimal
    tx_hash: str
    external: bool
    ts: int


@dataclass
class Ledger:
    entries: list[LedgerEntry] = field(default_factory=list)
    _sessions: set[str] = field(default_factory=set)

    def record(
        self,
        *,
        query_hash: str,
        agent_wallet: str,
        citations: list[CitationRecord],
        author_wallets: dict[str, str | None],
        external: bool,
    ) -> None:
        """Append the settled (cited) records of one answer. $0 skips are not ledgered."""
        self._sessions.add(agent_wallet)
        now = int(time.time())
        for c in citations:
            if not c.cited or not c.tx_hash:
                continue
            self.entries.append(
                LedgerEntry(
                    query_hash=query_hash,
                    source_url=c.source_url,
                    author_wallet=author_wallets.get(c.source_url),
                    g=c.g,
                    amount=c.amount,
                    tx_hash=c.tx_hash,
                    external=external,
                    ts=now,
                )
            )

    def _sum(self, entries: list[LedgerEntry]) -> str:
        return str(sum((e.amount for e in entries), start=Decimal(0)))

    def metrics(self) -> dict[str, object]:
        team = [e for e in self.entries if not e.external]
        ext = [e for e in self.entries if e.external]
        return {
            "total_settled_usdc": self._sum(self.entries),
            "citations_settled": len(self.entries),
            "distinct_author_wallets": len(
                {e.author_wallet for e in self.entries if e.author_wallet}
            ),
            "distinct_sessions": len(self._sessions),
            "team": {"citations": len(team), "settled_usdc": self._sum(team)},
            "external": {"citations": len(ext), "settled_usdc": self._sum(ext)},
            "external_share_pct": round(100 * len(ext) / len(self.entries), 1)
            if self.entries
            else 0.0,
        }

    def recent(self, limit: int = 50) -> list[dict[str, object]]:
        rows = sorted(self.entries, key=lambda e: e.ts, reverse=True)[:limit]
        return [
            {
                "source_url": e.source_url,
                "author_wallet": e.author_wallet,
                "g": e.g,
                "amount": str(e.amount),
                "tx_hash": e.tx_hash,
                "external": e.external,
                "ts": e.ts,
            }
            for e in rows
        ]
