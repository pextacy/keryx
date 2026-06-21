"""Treasury — track inflows to the agent's treasury and sweep them out.

Ported from circlefin/arc-fintech (multi-chain treasury management + rebalance/sweep): a
treasury accumulates inflows (here, prepaid-credit top-ups settle to it) and can be swept to
a destination wallet when the balance crosses a threshold — the offline analogue of
arc-fintech's bridge rebalance. Pure ledger (deposits in, sweeps out); the actual USDC move
on a sweep is the caller's rail settlement, recorded back via ``swept``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

_UNIT = Decimal("0.000001")


class TreasuryError(Exception):
    """Invalid treasury operation (non-positive deposit, sweep with nothing to move)."""


class FlowKind(enum.Enum):
    DEPOSIT = "deposit"
    SWEEP = "sweep"


@dataclass(frozen=True)
class Flow:
    """One treasury movement: a deposit in or a sweep out."""

    kind: FlowKind
    amount: Decimal
    counterparty: str  # source of a deposit, or destination of a sweep
    tx_hash: str | None


def _q(value: Decimal) -> Decimal:
    return value.quantize(_UNIT, rounding=ROUND_DOWN)


@dataclass
class Treasury:
    """The agent's treasury balance and its flow history."""

    wallet: str
    balance: Decimal = Decimal(0)
    flows: list[Flow] = field(default_factory=list)

    def deposit(self, amount: Decimal, source: str, tx_hash: str | None = None) -> Decimal:
        """Record an inflow (e.g. a credit top-up settled to the treasury). Returns new balance."""
        if amount <= 0:
            raise TreasuryError("deposit amount must be positive")
        amt = _q(amount)
        self.balance = _q(self.balance + amt)
        self.flows.append(
            Flow(kind=FlowKind.DEPOSIT, amount=amt, counterparty=source, tx_hash=tx_hash)
        )
        return self.balance

    def sweepable(self, threshold: Decimal) -> bool:
        """Whether the balance has crossed the sweep threshold (arc-fintech rebalance trigger)."""
        return self.balance >= threshold and self.balance > 0

    def prepare_sweep(self) -> Decimal:
        """The amount a sweep would move (the whole balance). Raises if nothing to sweep."""
        if self.balance <= 0:
            raise TreasuryError("nothing to sweep")
        return self.balance

    def swept(self, amount: Decimal, destination: str, tx_hash: str) -> Decimal:
        """Record a completed sweep (call after the settlement succeeds). Returns new balance."""
        amt = _q(amount)
        self.balance = _q(self.balance - amt)
        if self.balance < 0:
            self.balance = Decimal(0)
        self.flows.append(
            Flow(kind=FlowKind.SWEEP, amount=amt, counterparty=destination, tx_hash=tx_hash)
        )
        return self.balance
