"""Reputation bonds — reputation you post as collateral, not a score you ask to be trusted.

Prior Art 08 (Lepton hackathon) / RFB 3: a provider agent posts a USDC bond to stand behind
a match. If it underdelivers, the bond slashes to the wronged claimant; if it delivers, the
bond releases back to the provider. Reputation becomes capital at risk — far harder to fake
than a self-reported score, and the outcome feeds an ERC-8004 reputation signal.

This module is the pure state machine (post -> resolve). The caller settles a slash through
the rail and (optionally) records the reputation delta on-chain via ERC-8004.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import Decimal


class BondStatus(enum.StrEnum):
    POSTED = "posted"
    RELEASED = "released"  # provider delivered — bond returns to provider
    SLASHED = "slashed"  # provider underdelivered — bond pays the claimant


@dataclass(frozen=True)
class Bond:
    id: str
    provider: str
    claimant: str
    amount: Decimal
    status: BondStatus
    passed: bool | None = None  # None until resolved

    @property
    def reputation_delta(self) -> int:
        """Reputation impact once resolved: +100 on a pass, -100 on a slash, else 0."""
        if self.passed is None:
            return 0
        return 100 if self.passed else -100


class BondAlreadyResolved(RuntimeError):
    """A bond was resolved twice."""


@dataclass
class BondBook:
    """In-memory book of posted bonds (mirrors chain when the real escrow is live)."""

    _bonds: dict[str, Bond] = field(default_factory=dict)
    _seq: int = 0

    def post(self, *, provider: str, amount: Decimal, claimant: str) -> Bond:
        self._seq += 1
        bond = Bond(
            id=f"bond:{self._seq}",
            provider=provider,
            claimant=claimant,
            amount=amount,
            status=BondStatus.POSTED,
        )
        self._bonds[bond.id] = bond
        return bond

    def get(self, bond_id: str) -> Bond | None:
        return self._bonds.get(bond_id)

    def resolve(self, bond_id: str, *, passed: bool) -> Bond:
        """Resolve a posted bond: RELEASED on pass, SLASHED on fail. Idempotency-guarded."""
        bond = self._bonds.get(bond_id)
        if bond is None:
            raise KeyError(bond_id)
        if bond.status is not BondStatus.POSTED:
            raise BondAlreadyResolved(bond_id)
        resolved = Bond(
            id=bond.id,
            provider=bond.provider,
            claimant=bond.claimant,
            amount=bond.amount,
            status=BondStatus.RELEASED if passed else BondStatus.SLASHED,
            passed=passed,
        )
        self._bonds[bond_id] = resolved
        return resolved
