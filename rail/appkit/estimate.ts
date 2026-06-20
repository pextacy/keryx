/**
 * App Kit estimate helpers — pre-flight quotes before executing a bridge or swap.
 *
 * Keryx use: show the fee/route (including the CCTP path App Kit may pick) before paying an
 * author cross-chain or converting a payout, so the agent can budget against the quote.
 */
import { AppKit, BridgeChain } from "@circle-fin/app-kit";
import { ARC_CHAIN, type ArcAdapter } from "./appkit.ts";

/** Quote bridging USDC into Arc from another chain (no funds move). */
export function quoteBridge(
  kit: AppKit,
  fromAdapter: ArcAdapter,
  fromChain: BridgeChain | `${BridgeChain}`,
  toAdapter: ArcAdapter,
  amount: string,
) {
  return kit.estimateBridge({
    from: { adapter: fromAdapter, chain: fromChain },
    to: { adapter: toAdapter, chain: ARC_CHAIN },
    amount,
  });
}

/** Quote swapping one stablecoin for another on Arc (no funds move). Needs a Circle kit key. */
export function quoteSwap(
  kit: AppKit,
  adapter: ArcAdapter,
  tokenIn: string,
  tokenOut: string,
  amountIn: string,
  kitKey: string,
) {
  return kit.estimateSwap({
    from: { adapter, chain: ARC_CHAIN },
    tokenIn,
    tokenOut,
    amountIn,
    config: { kitKey },
  });
}
