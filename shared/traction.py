"""Traction — aggregate nanopayment volume across every Keryx primitive.

Traction is the 30%-weighted judging axis (Lepton hackathon): genuine usage with payments
actually flowing. The settlement ledger (agent/ledger.py) tracks citation tolls; this rolls
up volume from the newer primitives too — royalty splits, reputation-bond slashes, streaming
ticks, user-centric royalties, quadratic-funding matches — so one number tells the story.

In-memory, append-only counters; mirrors chain when the real rail is live.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class KindStat:
    count: int = 0
    volume: Decimal = Decimal(0)


@dataclass
class TractionBook:
    """Per-primitive settled-volume counters."""

    _by_kind: dict[str, KindStat] = field(default_factory=dict)

    def record(self, kind: str, amount: Decimal) -> None:
        """Record one settled payment of ``amount`` under ``kind`` (no-op for amount <= 0)."""
        if amount <= 0:
            return
        stat = self._by_kind.setdefault(kind, KindStat())
        stat.count += 1
        stat.volume += amount

    def summary(self) -> dict[str, object]:
        total_volume = sum((s.volume for s in self._by_kind.values()), Decimal(0))
        total_count = sum(s.count for s in self._by_kind.values())
        by_kind = {
            kind: {"count": s.count, "volume_usdc": str(s.volume)}
            for kind, s in sorted(self._by_kind.items())
        }
        return {
            "total_volume_usdc": str(total_volume),
            "total_payments": total_count,
            "by_kind": by_kind,
        }
