/**
 * App Kit Unified Balance — a chain-abstracted USDC balance for the paying agent.
 *
 * Keryx use: deposit USDC from multiple chains into one virtual balance, then spend it on
 * Arc to settle citations/jobs without per-chain liquidity management.
 */
import { AppKit, UnifiedBalanceChain } from "@circle-fin/app-kit";
import { ARC_CHAIN, type ArcAdapter } from "./appkit.ts";

type Token = "USDC";

/** Deposit USDC into the unified balance from a source chain. */
export function depositToBalance(
  kit: AppKit,
  adapter: ArcAdapter,
  fromChain: UnifiedBalanceChain | `${UnifiedBalanceChain}`,
  amount: string,
  token: Token = "USDC",
) {
  return kit.unifiedBalance.deposit({
    from: { adapter, chain: fromChain },
    amount,
    token,
  });
}

/** Spend from the unified balance to a recipient on Arc (e.g. an author payout). */
export function spendFromBalance(
  kit: AppKit,
  fromAdapter: ArcAdapter,
  toAdapter: ArcAdapter,
  recipientAddress: string,
  amountIn: string,
  token: Token = "USDC",
) {
  return kit.unifiedBalance.spend({
    from: { adapter: fromAdapter },
    amount: amountIn,
    to: { adapter: toAdapter, chain: ARC_CHAIN, recipientAddress },
    token,
  });
}

/** Read the unified USDC balance for the adapter's account. */
export function getUnifiedBalance(kit: AppKit, adapter: ArcAdapter, token: Token = "USDC") {
  return kit.unifiedBalance.getBalances({ token, sources: { adapter } });
}
