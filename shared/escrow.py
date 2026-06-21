"""Milestone escrow — lock a total, release it to the provider in approved tranches.

Ported from circlefin/arc-escrow (AI-validated escrow agreements that release funds as work is
approved): a client escrows a total split into named milestones; each milestone releases its
tranche to the provider once approved, settling through the rail. Generalises the single-shot
bond into staged delivery. Offline state machine — the real validation/release is the caller's
approval + rail settlement; this tracks the agreement and which tranches have paid out.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

_UNIT = Decimal("0.000001")


class EscrowError(Exception):
    """Invalid escrow operation (no milestones, bad index, already released)."""


class MilestoneStatus(enum.Enum):
    PENDING = "pending"
    RELEASED = "released"


class EscrowStatus(enum.Enum):
    OPEN = "open"
    COMPLETED = "completed"


@dataclass
class Milestone:
    """One tranche of an escrow: a labelled amount that releases to the provider on approval."""

    label: str
    amount: Decimal
    status: MilestoneStatus = MilestoneStatus.PENDING
    tx_hash: str | None = None


@dataclass
class Escrow:
    """A client→provider agreement whose total releases across approved milestones."""

    id: str
    client: str
    provider: str
    milestones: list[Milestone]

    @property
    def total(self) -> Decimal:
        return sum((m.amount for m in self.milestones), Decimal(0))

    @property
    def status(self) -> EscrowStatus:
        done = all(m.status is MilestoneStatus.RELEASED for m in self.milestones)
        return EscrowStatus.COMPLETED if done else EscrowStatus.OPEN

    def released(self) -> Decimal:
        return sum(
            (m.amount for m in self.milestones if m.status is MilestoneStatus.RELEASED),
            Decimal(0),
        )

    def locked(self) -> Decimal:
        return self.total - self.released()


def _q(value: Decimal) -> Decimal:
    return value.quantize(_UNIT, rounding=ROUND_DOWN)


@dataclass
class EscrowBook:
    """Milestone escrows keyed by id. Deterministic ids (``esc-1``…) for reproducibility."""

    _escrows: dict[str, Escrow] = field(default_factory=dict)
    _counter: int = 0

    def create(self, client: str, provider: str, milestones: list[tuple[str, Decimal]]) -> Escrow:
        """Open an escrow from (label, amount) milestone pairs. Raises if empty or non-positive."""
        if not milestones:
            raise EscrowError("an escrow needs at least one milestone")
        items = []
        for label, amount in milestones:
            if amount <= 0:
                raise EscrowError(f"milestone {label!r} amount must be positive")
            items.append(Milestone(label=label, amount=_q(amount)))
        self._counter += 1
        eid = f"esc-{self._counter}"
        escrow = Escrow(id=eid, client=client, provider=provider, milestones=items)
        self._escrows[eid] = escrow
        return escrow

    def get(self, eid: str) -> Escrow | None:
        return self._escrows.get(eid)

    def prepare_release(self, eid: str, index: int) -> Milestone:
        """Validate a milestone release without mutating it. Raises if unknown/out-of-range/paid."""
        escrow = self._escrows.get(eid)
        if escrow is None:
            raise EscrowError(f"unknown escrow {eid!r}")
        if index < 0 or index >= len(escrow.milestones):
            raise EscrowError(f"milestone index {index} out of range for {eid}")
        milestone = escrow.milestones[index]
        if milestone.status is MilestoneStatus.RELEASED:
            raise EscrowError(f"milestone {index} of {eid} already released")
        return milestone

    def released(self, milestone: Milestone, tx_hash: str) -> None:
        """Record a successful release against a milestone (marks it released)."""
        milestone.status = MilestoneStatus.RELEASED
        milestone.tx_hash = tx_hash

    def summary(self) -> dict[str, object]:
        """Aggregate position: open count and total still locked across all escrows."""
        escrows = self._escrows.values()
        open_count = sum(1 for e in escrows if e.status is EscrowStatus.OPEN)
        locked = sum((e.locked() for e in escrows), Decimal(0))
        return {"total": len(self._escrows), "open": open_count, "locked_usdc": str(_q(locked))}
