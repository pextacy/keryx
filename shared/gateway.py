"""Gateway unified balance — deposit USDC from many chains into one Arc-spendable balance.

Ported from circlefin/arc-multichain-wallet (Circle Gateway unified balance): a wallet
deposits USDC from several source chains (Arc Testnet, Avalanche Fuji, Base Sepolia) into a
single virtual balance it can spend on Arc, without per-chain liquidity management. Here the
cross-chain move is mocked (the real path is Circle Gateway via rail/appkit unified-balance);
this models the unified balance + its per-chain provenance so the agent can fund settlements
from a chain-abstracted pool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

_UNIT = Decimal("0.000001")

# Source chains a deposit can originate from (arc-multichain-wallet's SupportedChain set).
SUPPORTED_CHAINS = ("arcTestnet", "avalancheFuji", "baseSepolia")


class GatewayError(Exception):
    """Invalid gateway operation (unknown chain, non-positive amount)."""


@dataclass(frozen=True)
class Deposit:
    """One cross-chain deposit into the unified balance."""

    chain: str
    amount: Decimal
    tx_hash: str | None


@dataclass(frozen=True)
class Withdrawal:
    """One cross-chain transfer out of the unified balance (burn here, mint on ``chain``)."""

    chain: str
    amount: Decimal
    recipient: str
    tx_hash: str | None


@dataclass
class UnifiedAccount:
    """A wallet's unified balance plus its deposit (in) and withdrawal (out) provenance."""

    wallet: str
    balance: Decimal = Decimal(0)
    by_chain: dict[str, Decimal] = field(default_factory=dict)
    deposits: list[Deposit] = field(default_factory=list)
    withdrawals: list[Withdrawal] = field(default_factory=list)


def _q(value: Decimal) -> Decimal:
    return value.quantize(_UNIT, rounding=ROUND_DOWN)


def normalize_chain(chain: str) -> str:
    """Resolve a chain name case-insensitively to the canonical SupportedChain id."""
    c = chain.strip()
    for known in SUPPORTED_CHAINS:
        if c.lower() == known.lower():
            return known
    raise GatewayError(
        f"unsupported chain {chain!r}; expected one of {', '.join(SUPPORTED_CHAINS)}"
    )


@dataclass
class GatewayBook:
    """Unified Gateway balances keyed by wallet."""

    _accounts: dict[str, UnifiedAccount] = field(default_factory=dict)

    def account(self, wallet: str) -> UnifiedAccount:
        acct = self._accounts.get(wallet)
        if acct is None:
            acct = UnifiedAccount(wallet=wallet)
            self._accounts[wallet] = acct
        return acct

    def get(self, wallet: str) -> UnifiedAccount | None:
        return self._accounts.get(wallet)

    def deposit(
        self, wallet: str, chain: str, amount: Decimal, tx_hash: str | None = None
    ) -> UnifiedAccount:
        """Credit a cross-chain deposit into the wallet's unified balance (chain validated)."""
        canonical = normalize_chain(chain)
        if amount <= 0:
            raise GatewayError("deposit amount must be positive")
        acct = self.account(wallet)
        amt = _q(amount)
        acct.balance = _q(acct.balance + amt)
        acct.by_chain[canonical] = _q(acct.by_chain.get(canonical, Decimal(0)) + amt)
        acct.deposits.append(Deposit(chain=canonical, amount=amt, tx_hash=tx_hash))
        return acct

    def prepare_spend(self, wallet: str, amount: Decimal) -> Decimal:
        """Validate a spend against the unified balance without mutating it (chain-abstracted
        ``kit.unifiedBalance.spend``). Raises GatewayError if insufficient. Returns the amount."""
        if amount <= 0:
            raise GatewayError("spend amount must be positive")
        acct = self.account(wallet)
        amt = _q(amount)
        if amt > acct.balance:
            raise GatewayError(f"insufficient_balance: have {acct.balance}, need {amt}")
        return amt

    def settled_spend(self, wallet: str, amount: Decimal) -> UnifiedAccount:
        """Draw the spent amount down from the unified balance (call after settlement succeeds)."""
        acct = self.account(wallet)
        acct.balance = _q(acct.balance - _q(amount))
        if acct.balance < 0:
            acct.balance = Decimal(0)
        return acct

    def prepare_transfer(self, wallet: str, dest_chain: str, amount: Decimal) -> Decimal:
        """Validate a cross-chain transfer out of the unified balance without mutating it
        (arc-multichain-wallet's burn/mint move). Checks the destination chain is supported and
        the unified balance covers it. Raises GatewayError otherwise; returns the amount."""
        normalize_chain(dest_chain)  # reject unknown destination before any settlement
        return self.prepare_spend(wallet, amount)

    def settled_transfer(
        self,
        wallet: str,
        amount: Decimal,
        dest_chain: str,
        recipient: str,
        tx_hash: str | None = None,
    ) -> UnifiedAccount:
        """Burn ``amount`` from the unified balance and record the mint on ``dest_chain`` to
        ``recipient`` (call after settlement succeeds). Mirrors settled_spend's draw-down."""
        canonical = normalize_chain(dest_chain)
        acct = self.settled_spend(wallet, amount)
        acct.withdrawals.append(
            Withdrawal(chain=canonical, amount=_q(amount), recipient=recipient, tx_hash=tx_hash)
        )
        return acct

    def summary(self) -> dict[str, object]:
        """Aggregate unified position: total balance and account count across the gateway."""
        total = sum((a.balance for a in self._accounts.values()), Decimal(0))
        return {"accounts": len(self._accounts), "unified_usdc": str(_q(total))}
