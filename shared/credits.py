"""Prepaid credits — top up USDC once, draw down per action.

Ported from circlefin/arc-commerce (buy credits with USDC on Arc, then spend them): an agent
prepays into a credit balance via a single settlement, then draws the balance down per action
(e.g. one citation toll) with no further on-chain move. This batches many micro-tolls into one
settlement — the agent-web equivalent of buying API credits.

USDC settles only on top-up (the caller settles to a treasury and records it via ``credit``);
spends are pure balance draws. Offline state machine, 6-dp USDC, no clock/randomness.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

_UNIT = Decimal("0.000001")


class CreditError(Exception):
    """Invalid credit operation (non-positive amount, insufficient balance)."""


class EntryKind(enum.Enum):
    TOPUP = "topup"
    SPEND = "spend"


@dataclass(frozen=True)
class CreditEntry:
    """One movement on a credit account."""

    kind: EntryKind
    amount: Decimal
    reason: str
    tx_hash: str | None  # the settlement tx for a top-up; None for a spend


@dataclass
class CreditAccount:
    """A wallet's prepaid balance and its movement history."""

    wallet: str
    balance: Decimal = Decimal(0)
    entries: list[CreditEntry] = field(default_factory=list)


def _q(value: Decimal) -> Decimal:
    return value.quantize(_UNIT, rounding=ROUND_DOWN)


@dataclass
class CreditBook:
    """Prepaid credit accounts keyed by wallet."""

    _accounts: dict[str, CreditAccount] = field(default_factory=dict)

    def account(self, wallet: str) -> CreditAccount:
        acct = self._accounts.get(wallet)
        if acct is None:
            acct = CreditAccount(wallet=wallet)
            self._accounts[wallet] = acct
        return acct

    def get(self, wallet: str) -> CreditAccount | None:
        return self._accounts.get(wallet)

    def summary(self) -> dict[str, object]:
        """Aggregate prepaid position: total credits held and how many accounts hold them."""
        total = sum((a.balance for a in self._accounts.values()), Decimal(0))
        return {"accounts": len(self._accounts), "outstanding_usdc": str(_q(total))}

    def credit(self, wallet: str, amount: Decimal, tx_hash: str) -> CreditAccount:
        """Add prepaid credits after a successful top-up settlement (tx already settled)."""
        if amount <= 0:
            raise CreditError("top-up amount must be positive")
        acct = self.account(wallet)
        amt = _q(amount)
        acct.balance = _q(acct.balance + amt)
        acct.entries.append(
            CreditEntry(kind=EntryKind.TOPUP, amount=amt, reason="topup", tx_hash=tx_hash)
        )
        return acct

    def spend(self, wallet: str, amount: Decimal, reason: str) -> CreditAccount:
        """Draw down credits for an action. Raises CreditError if the balance is too low."""
        if amount <= 0:
            raise CreditError("spend amount must be positive")
        acct = self.account(wallet)
        amt = _q(amount)
        if amt > acct.balance:
            raise CreditError(f"insufficient_credits: have {acct.balance}, need {amt}")
        acct.balance = _q(acct.balance - amt)
        acct.entries.append(
            CreditEntry(kind=EntryKind.SPEND, amount=amt, reason=reason or "spend", tx_hash=None)
        )
        return acct
