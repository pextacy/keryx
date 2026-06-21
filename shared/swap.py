"""Stablecoin FX swap — offline quote + execute (USDC <-> EURC on Arc).

Ports the shape of circlefin/arc-stablecoin-fx (src/lib/appkit/swap.ts): an
``estimateSwap`` returning {amountOut, appFeeBps, effectiveRate} and an ``executeSwap``
returning a tx. Here the App Kit ``kit.swap()`` call is replaced by an offline FX engine
so the capability is exercisable with zero funds; the real on-chain swap is the
``swapOnArc`` App Kit path in rail/appkit (kit key + funds gated, not wired here).

The fee model mirrors arc-stablecoin-fx's ``customFee.percentageBps``: a basis-point app
fee is taken off the gross converted amount. Amounts are USDC/EURC (6 decimals); math is
Decimal and quantized to 6 places (no float drift).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

# Supported stablecoins on the Arc testnet FX pair.
TOKENS = ("USDC", "EURC")
_UNIT = Decimal("0.000001")  # 6 decimals
_BPS = Decimal(10_000)

# Mock mid-market rates (offline). 1 unit of [base] -> [quote] amount. Inverses are exact
# reciprocals so a round-trip differs only by the app fee, not by rate asymmetry.
_RATE_USDC_EURC = Decimal("0.92")  # 1 USDC -> 0.92 EURC (illustrative testnet rate)
_RATES: dict[tuple[str, str], Decimal] = {
    ("USDC", "EURC"): _RATE_USDC_EURC,
    ("EURC", "USDC"): (Decimal(1) / _RATE_USDC_EURC),
    ("USDC", "USDC"): Decimal(1),
    ("EURC", "EURC"): Decimal(1),
}


class SwapError(ValueError):
    """Invalid swap request (unknown token, non-positive amount)."""


@dataclass(frozen=True)
class SwapQuote:
    """Result of estimateSwap: net out after the app fee, plus the rate that produced it."""

    token_in: str
    token_out: str
    amount_in: Decimal
    amount_out: Decimal  # net of app fee
    app_fee_bps: int
    app_fee: Decimal  # in token_out units
    effective_rate: Decimal  # amount_out / amount_in (net)


def _norm_token(token: str) -> str:
    t = token.strip().upper()
    if t not in TOKENS:
        raise SwapError(f"unsupported token {token!r}; expected one of {', '.join(TOKENS)}")
    return t


def _q(value: Decimal) -> Decimal:
    return value.quantize(_UNIT, rounding=ROUND_DOWN)


def quote(token_in: str, token_out: str, amount_in: Decimal, app_fee_bps: int) -> SwapQuote:
    """Estimate a swap: gross = amount_in * rate, then take app_fee_bps off the gross.

    Mirrors arc-stablecoin-fx estimateSwap + customFee. Raises SwapError on bad input.
    """
    ti, to = _norm_token(token_in), _norm_token(token_out)
    if amount_in <= 0:
        raise SwapError("amount_in must be positive")
    if app_fee_bps < 0 or app_fee_bps > 10_000:
        raise SwapError("app_fee_bps must be within [0, 10000]")
    rate = _RATES[(ti, to)]
    gross = amount_in * rate
    fee = _q(gross * Decimal(app_fee_bps) / _BPS)
    net = _q(gross) - fee
    if net < 0:
        net = Decimal(0)
    effective = (net / amount_in) if amount_in > 0 else Decimal(0)
    return SwapQuote(
        token_in=ti,
        token_out=to,
        amount_in=_q(amount_in),
        amount_out=net,
        app_fee_bps=app_fee_bps,
        app_fee=fee,
        effective_rate=effective,
    )
