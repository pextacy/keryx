"""Orders — bundle several line-items into one checkout (multi-recipient purchase).

Ported from circlefin/arc-commerce (USDC checkout): there a checkout buys credits in one
settlement. Keryx generalises it to a multi-item order — each line-item pays a different
recipient (e.g. a research bundle: the source author + the validator + the indexer) — settled
together at checkout and returned as one receipt with per-item tx hashes. Offline state
machine; the USDC move is the caller's rail settlement, recorded back via ``paid``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

_UNIT = Decimal("0.000001")


class OrderError(Exception):
    """Invalid order operation (no items, non-positive amount, already checked out)."""


class OrderStatus(enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    PARTIAL = "partial"  # checkout ran but some line-items failed to settle


@dataclass
class LineItem:
    """One line of an order: who gets paid, how much, and for what."""

    description: str
    to: str
    amount: Decimal
    tx_hash: str | None = None

    @property
    def paid(self) -> bool:
        return self.tx_hash is not None


@dataclass
class Order:
    """A multi-recipient order settled together at checkout."""

    id: str
    items: list[LineItem]
    checked_out: bool = False

    @property
    def total(self) -> Decimal:
        return sum((i.amount for i in self.items), Decimal(0))

    @property
    def status(self) -> OrderStatus:
        if not self.checked_out:
            return OrderStatus.PENDING
        return OrderStatus.PAID if all(i.paid for i in self.items) else OrderStatus.PARTIAL

    def paid_total(self) -> Decimal:
        return sum((i.amount for i in self.items if i.paid), Decimal(0))


def _q(value: Decimal) -> Decimal:
    return value.quantize(_UNIT, rounding=ROUND_DOWN)


@dataclass
class OrderBook:
    """Multi-item orders keyed by id. Deterministic ids (``ord-1``…) for reproducibility."""

    _orders: dict[str, Order] = field(default_factory=dict)
    _counter: int = 0

    def create(self, items: list[tuple[str, str, Decimal]]) -> Order:
        """Open a pending order from (description, to, amount) line-items. Raises if empty/bad."""
        if not items:
            raise OrderError("an order needs at least one line-item")
        lines = []
        for description, to, amount in items:
            if amount <= 0:
                raise OrderError(f"line-item {description!r} amount must be positive")
            lines.append(LineItem(description=description, to=to, amount=_q(amount)))
        self._counter += 1
        oid = f"ord-{self._counter}"
        order = Order(id=oid, items=lines)
        self._orders[oid] = order
        return order

    def get(self, oid: str) -> Order | None:
        return self._orders.get(oid)

    def begin_checkout(self, oid: str) -> Order:
        """Mark an order as checked out (so settlements can be recorded). Raises if re-run."""
        order = self._orders.get(oid)
        if order is None:
            raise OrderError(f"unknown order {oid!r}")
        if order.checked_out:
            raise OrderError(f"order {oid!r} already checked out")
        order.checked_out = True
        return order

    def summary(self) -> dict[str, object]:
        """Aggregate position: open (pending) count and total still unpaid."""
        orders = self._orders.values()
        pending = [o for o in orders if o.status is OrderStatus.PENDING]
        unpaid = sum((o.total - o.paid_total() for o in orders if not o.checked_out), Decimal(0))
        return {"total": len(self._orders), "pending": len(pending), "unpaid_usdc": str(_q(unpaid))}
