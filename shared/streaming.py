"""Streaming payments — you pay for the rate of flow, by the second.

RFB 4 / Prior Art 06 (Lepton hackathon): continuous authorization for live media/compute.
A payer approves a rate (USDC per second) instead of a price; the stream bills per second
watched and accrues in real time. Sub-micro fractions carry across ticks, so over a long
stream there is no dust and we never overpay — only whole micro-USDC ever settle.

Pure state machine (open -> tick/pause/resume -> close); the caller settles each increment
through the rail. ``tick`` takes an explicit duration so billing is deterministic.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

from shared.types import USDC_DECIMALS

_Q = Decimal(1).scaleb(-USDC_DECIMALS)  # one micro-USDC


class StreamStatus(enum.StrEnum):
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"


@dataclass
class Stream:
    id: str
    payer: str
    payee: str
    rate: Decimal  # USDC per second
    status: StreamStatus = StreamStatus.OPEN
    accrued: Decimal = Decimal(0)  # exact value owed (incl. sub-micro fraction)
    settled: Decimal = Decimal(0)  # micro-USDC already billed


class StreamClosed(RuntimeError):
    """An operation was attempted on a closed stream."""


@dataclass
class StreamBook:
    """In-memory book of streams; bills whole micro-USDC with fractional carry."""

    _streams: dict[str, Stream] = field(default_factory=dict)
    _seq: int = 0

    def open(self, *, payer: str, payee: str, rate: Decimal) -> Stream:
        self._seq += 1
        s = Stream(id=f"stream:{self._seq}", payer=payer, payee=payee, rate=rate)
        self._streams[s.id] = s
        return s

    def get(self, stream_id: str) -> Stream | None:
        return self._streams.get(stream_id)

    def _billable(self, s: Stream) -> Decimal:
        """Whole micro-USDC now owed beyond what's settled (carries the fraction).

        Pure — does NOT advance ``settled``. The caller settles ``due`` through the rail
        and only then calls :meth:`commit`, so a failed settlement is re-billed next time
        instead of being silently marked paid and lost.
        """
        micro = s.accrued.quantize(_Q, rounding=ROUND_DOWN)
        return micro - s.settled

    def commit(self, stream_id: str, amount: Decimal) -> None:
        """Advance ``settled`` by ``amount`` once the rail confirms the payment cleared."""
        s = self._streams.get(stream_id)  # works on closed streams (final tick commits)
        if s is None:
            raise KeyError(stream_id)
        if amount > 0:
            s.settled += amount

    def tick(self, stream_id: str, seconds: Decimal) -> Decimal:
        """Accrue ``seconds`` of flow on an OPEN stream; return the newly-billable amount.

        A paused stream accrues nothing. Returns 0 when the increment is sub-micro (carried).
        Does not advance ``settled`` — the caller settles, then calls :meth:`commit`.
        """
        s = self._require(stream_id)
        if s.status is StreamStatus.OPEN and seconds > 0:
            s.accrued += s.rate * seconds
        return self._billable(s)

    def pause(self, stream_id: str) -> Stream:
        s = self._require(stream_id)
        if s.status is StreamStatus.OPEN:
            s.status = StreamStatus.PAUSED
        return s

    def resume(self, stream_id: str) -> Stream:
        s = self._require(stream_id)
        if s.status is StreamStatus.PAUSED:
            s.status = StreamStatus.OPEN
        return s

    def close(self, stream_id: str) -> tuple[Stream, Decimal]:
        """Close the stream; return it plus any final billable micro-USDC."""
        s = self._require(stream_id)
        due = self._billable(s)
        s.status = StreamStatus.CLOSED
        return s, due

    def _require(self, stream_id: str) -> Stream:
        s = self._streams.get(stream_id)
        if s is None:
            raise KeyError(stream_id)
        if s.status is StreamStatus.CLOSED:
            raise StreamClosed(stream_id)
        return s
