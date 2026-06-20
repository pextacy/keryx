"""Quadratic funding — a thousand small backers outweigh one large one.

Prior Art 03/07 (Lepton hackathon): a match pool distributed by breadth of support, not its
size. A project's match weight is ``(Σ √contribution)²`` — the canonical quadratic-funding
formula — so many small contributions beat a single big one. The pool is apportioned across
projects by those weights, dust-free, summing exactly to the pool (reuses the splits layer).

Pure and offline; the caller settles each project's match through the rail.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal

from shared.splits import split_amount


@dataclass(frozen=True)
class Project:
    wallet: str
    contributions: list[Decimal] = field(default_factory=list)


def match_weight(contributions: list[Decimal]) -> Decimal:
    """Quadratic-funding weight ``(Σ √c)²`` over positive contributions."""
    root_sum = sum(math.sqrt(float(c)) for c in contributions if c > 0)
    return Decimal(str(root_sum * root_sum))


def quadratic_match(pool: Decimal, projects: list[Project]) -> list[tuple[Project, Decimal]]:
    """Apportion ``pool`` across projects by quadratic weight, summing exactly to the pool.

    Projects with no positive contributions get nothing; the rest share the whole pool with
    no dust (largest-remainder via :func:`shared.splits.split_amount`).
    """
    weights = [match_weight(p.contributions) for p in projects]
    eligible = [i for i, w in enumerate(weights) if w > 0]
    result: list[Decimal] = [Decimal(0)] * len(projects)
    if eligible:
        amounts = split_amount(pool, [weights[i] for i in eligible])
        for i, amt in zip(eligible, amounts, strict=True):
            result[i] = amt
    return list(zip(projects, result, strict=True))
