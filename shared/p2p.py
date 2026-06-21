"""Split-bill money requests — P2P "request money" as a settlement primitive.

Inspired by circlefin/arc-p2p-payments (gasless P2P USDC on Arc): there one wallet pays
another. Keryx generalizes it to a *request*: a payee asks a set of payers to cover a total,
split dust-free across them; each payer fulfils their share, which settles to the payee. The
request is settled once every share is in. Fits the agent web — e.g. splitting a citation
toll across co-authors, or an agent requesting reimbursement from several beneficiaries.

Pure offline state machine (no clock/randomness, deterministic ids ``req-1``…); the actual
USDC move is the caller's rail settlement, recorded back via ``fulfil``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import Decimal

from shared.splits import split_amount


class RequestStatus(enum.Enum):
    OPEN = "open"
    SETTLED = "settled"


class RequestError(Exception):
    """Invalid request operation (unknown payer, already paid, no payers)."""


@dataclass
class Share:
    """One payer's portion of a request."""

    payer: str
    amount: Decimal
    paid: bool = False
    tx_hash: str | None = None


@dataclass
class PaymentRequest:
    """A payee's money request, split dust-free across payers."""

    id: str
    payee: str
    total: Decimal
    shares: list[Share]

    @property
    def status(self) -> RequestStatus:
        return RequestStatus.SETTLED if all(s.paid for s in self.shares) else RequestStatus.OPEN

    def collected(self) -> Decimal:
        return sum((s.amount for s in self.shares if s.paid), Decimal(0))

    def outstanding(self) -> Decimal:
        return sum((s.amount for s in self.shares if not s.paid), Decimal(0))

    def find(self, payer: str) -> Share:
        for s in self.shares:
            if s.payer == payer:
                return s
        raise RequestError(f"{payer!r} is not a payer on {self.id}")


@dataclass
class RequestBook:
    """Holds open/settled money requests. Deterministic ids so the flow is reproducible."""

    _requests: dict[str, PaymentRequest] = field(default_factory=dict)
    _counter: int = 0

    def create(self, payee: str, payers: list[str], total: Decimal) -> PaymentRequest:
        """Open a request: split ``total`` equally (dust-free) across ``payers``."""
        if not payers:
            raise RequestError("a request needs at least one payer")
        if total <= 0:
            raise RequestError("total must be positive")
        amounts = split_amount(total, [Decimal(1)] * len(payers))
        shares = [Share(payer=p, amount=a) for p, a in zip(payers, amounts, strict=True)]
        self._counter += 1
        rid = f"req-{self._counter}"
        req = PaymentRequest(id=rid, payee=payee, total=total, shares=shares)
        self._requests[rid] = req
        return req

    def get(self, rid: str) -> PaymentRequest | None:
        return self._requests.get(rid)

    def fulfil(self, rid: str, payer: str) -> Share:
        """Mark a payer's share as the next to settle. Raises if unknown or already paid.

        The caller settles ``share.amount`` to the request's payee, then records the tx via
        :meth:`settled`. Kept two-step so a failed settlement never marks the share paid.
        """
        req = self._requests.get(rid)
        if req is None:
            raise RequestError(f"unknown request {rid!r}")
        share = req.find(payer)
        if share.paid:
            raise RequestError(f"{payer!r} already paid {rid}")
        return share

    def settled(self, share: Share, tx_hash: str) -> None:
        """Record a successful settlement against a share (marks it paid)."""
        share.paid = True
        share.tx_hash = tx_hash
