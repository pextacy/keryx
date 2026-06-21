"""Traction — aggregate nanopayment volume across every Keryx primitive.

Traction is the 30%-weighted judging axis (Lepton hackathon): genuine usage with payments
actually flowing. The settlement ledger (agent/ledger.py) tracks citation tolls; this rolls
up volume from the newer primitives too — royalty splits, reputation-bond slashes, streaming
ticks, user-centric royalties, quadratic-funding matches — so one number tells the story.

In-memory, append-only counters; mirrors chain when the real rail is live.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal

# How many recent settlements to retain for the /history feed (bounded — aggregates are
# canonical; this is a rolling window for the dashboard).
_HISTORY_CAP = 500


@dataclass
class KindStat:
    count: int = 0
    volume: Decimal = Decimal(0)


@dataclass(frozen=True)
class Settlement:
    """One settled payment in the recent-history window."""

    seq: int
    kind: str
    amount: Decimal
    wallet: str
    tx_hash: str | None


@dataclass
class TractionBook:
    """Per-primitive settled-volume counters plus a rolling recent-settlements log."""

    _by_kind: dict[str, KindStat] = field(default_factory=dict)
    _history: deque[Settlement] = field(default_factory=lambda: deque(maxlen=_HISTORY_CAP))
    _seq: int = 0

    def record(
        self, kind: str, amount: Decimal, wallet: str = "", tx_hash: str | None = None
    ) -> None:
        """Record one settled payment of ``amount`` under ``kind`` (no-op for amount <= 0).

        Also appends to the bounded recent-settlements log (the /history feed)."""
        if amount <= 0:
            return
        stat = self._by_kind.setdefault(kind, KindStat())
        stat.count += 1
        stat.volume += amount
        self._seq += 1
        self._history.append(
            Settlement(seq=self._seq, kind=kind, amount=amount, wallet=wallet, tx_hash=tx_hash)
        )

    def recent(self, limit: int = 50, kind: str = "") -> list[dict[str, object]]:
        """Recent settlements (most recent first), optionally filtered by ``kind``."""
        items = reversed(self._history)
        out: list[dict[str, object]] = []
        for s in items:
            if kind and s.kind != kind:
                continue
            out.append(
                {
                    "seq": s.seq,
                    "kind": s.kind,
                    "amount": str(s.amount),
                    "wallet": s.wallet,
                    "tx_hash": s.tx_hash,
                }
            )
            if len(out) >= max(0, limit):
                break
        return out

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
