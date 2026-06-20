"""Royalty splits — pay every credited contributor in the proportions the metadata records.

Prior Art 04 (Lepton hackathon): a citation payment that follows a work back through everyone
who made it. Given a total and weighted contributors (the attribution graph: writer, editor,
photographer, …), split the amount across them quantized to USDC precision, summing EXACTLY
to the total — largest-remainder apportionment, so there is no dust and we never overpay.

Pure and offline; the caller settles the resulting shares through the rail.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from shared.types import USDC_DECIMALS

# One micro-USDC — the settlement quantum (6 decimals).
_Q = Decimal(1).scaleb(-USDC_DECIMALS)


@dataclass(frozen=True)
class Contributor:
    """One payee in an attribution graph: a wallet and a relative weight (any positive number)."""

    wallet: str
    weight: Decimal


def split_amount(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split ``total`` across positive ``weights``, each quantized to 6-dp USDC.

    Uses the largest-remainder method so ``sum(result) == total`` exactly (down to the
    micro-USDC), distributing leftover micro-units to the largest fractional remainders.
    Never produces dust and never exceeds ``total``.
    """
    if not weights or any(w <= 0 for w in weights):
        raise ValueError("weights must be non-empty and all positive")
    total_q = total.quantize(_Q, rounding=ROUND_DOWN)
    units = int((total_q / _Q).to_integral_value())  # total in micro-USDC
    wsum = sum(weights, Decimal(0))
    raw = [units * w / wsum for w in weights]
    floors = [int(r // 1) for r in raw]
    remainder = units - sum(floors)
    # Hand the leftover units to the largest fractional parts (ties: larger weight first).
    order = sorted(
        range(len(weights)),
        key=lambda i: (raw[i] - floors[i], weights[i]),
        reverse=True,
    )
    for i in range(remainder):
        floors[order[i]] += 1
    return [Decimal(f) * _Q for f in floors]


def split_payout(
    total: Decimal, contributors: list[Contributor]
) -> list[tuple[Contributor, Decimal]]:
    """Pair each contributor with its share of ``total`` (see :func:`split_amount`)."""
    amounts = split_amount(total, [c.weight for c in contributors])
    return list(zip(contributors, amounts, strict=True))
