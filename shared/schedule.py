"""Payment schedules — recurring fixed-amount payments (subscription / payroll style).

A treasury staple from circlefin/arc-fintech (scheduled multi-chain payouts): a payer commits
to pay a payee a fixed amount for a number of runs. Each run settles one installment through
the rail; the schedule completes when every run is paid (or is cancelled early). This is the
discrete counterpart to streaming (shared/streaming.py): streaming bills continuously per
second, a schedule pays a fixed amount per discrete run. Offline state machine — runs are
advanced explicitly (no clock), so the flow is reproducible.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import Decimal


class ScheduleError(Exception):
    """Invalid schedule operation (non-positive amount/runs, exhausted, cancelled)."""


class ScheduleStatus(enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class PaymentSchedule:
    """A payer→payee commitment of ``amount`` per run, for ``total_runs`` runs."""

    id: str
    payer: str
    payee: str
    amount: Decimal
    total_runs: int
    runs_done: int = 0
    cancelled: bool = False
    tx_hashes: list[str] = field(default_factory=list)

    @property
    def status(self) -> ScheduleStatus:
        if self.cancelled:
            return ScheduleStatus.CANCELLED
        return (
            ScheduleStatus.COMPLETED if self.runs_done >= self.total_runs else ScheduleStatus.ACTIVE
        )

    @property
    def runs_left(self) -> int:
        return max(0, self.total_runs - self.runs_done)

    def paid_total(self) -> Decimal:
        return self.amount * self.runs_done

    def remaining_total(self) -> Decimal:
        return self.amount * self.runs_left


@dataclass
class ScheduleBook:
    """Recurring payment schedules keyed by id. Deterministic ids (``sch-1``…)."""

    _schedules: dict[str, PaymentSchedule] = field(default_factory=dict)
    _counter: int = 0

    def create(self, payer: str, payee: str, amount: Decimal, total_runs: int) -> PaymentSchedule:
        """Open an active schedule. Raises if amount or run count is non-positive."""
        if amount <= 0:
            raise ScheduleError("amount must be positive")
        if total_runs <= 0:
            raise ScheduleError("total_runs must be positive")
        self._counter += 1
        sid = f"sch-{self._counter}"
        schedule = PaymentSchedule(
            id=sid, payer=payer, payee=payee, amount=amount, total_runs=total_runs
        )
        self._schedules[sid] = schedule
        return schedule

    def get(self, sid: str) -> PaymentSchedule | None:
        return self._schedules.get(sid)

    def prepare_run(self, sid: str) -> PaymentSchedule:
        """Validate that the next installment can run (without mutating). Raises otherwise."""
        schedule = self._schedules.get(sid)
        if schedule is None:
            raise ScheduleError(f"unknown schedule {sid!r}")
        if schedule.status is ScheduleStatus.CANCELLED:
            raise ScheduleError(f"schedule {sid!r} was cancelled")
        if schedule.status is ScheduleStatus.COMPLETED:
            raise ScheduleError(f"schedule {sid!r} has no runs left")
        return schedule

    def ran(self, schedule: PaymentSchedule, tx_hash: str) -> None:
        """Record a settled installment (call after the rail settlement succeeds)."""
        schedule.runs_done += 1
        schedule.tx_hashes.append(tx_hash)

    def cancel(self, sid: str) -> PaymentSchedule:
        schedule = self._schedules.get(sid)
        if schedule is None:
            raise ScheduleError(f"unknown schedule {sid!r}")
        schedule.cancelled = True
        return schedule

    def summary(self) -> dict[str, object]:
        """Aggregate position: active count and total still committed (unpaid future runs)."""
        active = [s for s in self._schedules.values() if s.status is ScheduleStatus.ACTIVE]
        committed = sum((s.remaining_total() for s in active), Decimal(0))
        return {
            "total": len(self._schedules),
            "active": len(active),
            "committed_usdc": str(committed),
        }
