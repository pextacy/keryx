/**
 * App Kit rail capabilities for Keryx — Send / Bridge / Swap USDC on Arc.
 *
 * A higher-level complement to the x402+Gateway settlement path (rail/m0_spike): one
 * type-safe interface over Circle's payment+liquidity protocols. For Keryx this gives:
 *   - send():   pay an author directly (P2P USDC transfer) — an alternative to the
 *               Gateway-batched citation toll for one-off payouts.
 *   - bridge(): fund the paying-agent wallet on Arc from another chain.
 *   - swap():   convert an author payout USDC <-> EURC on Arc.
 *
 * The viem adapter is wired to Keryx's configured Arc RPC (ARC_RPC_URL) so wallet and
 * read clients hit the same node as the rest of the rail. Nothing here runs until called
 * with a funded key — import is side-effect free.
 *
 * Docs: https://docs.arc.io/app-kit
 */
import { AppKit, BridgeChain } from "@circle-fin/app-kit";
import { createViemAdapterFromPrivateKey } from "@circle-fin/adapter-viem-v2";
import { createPublicClient, createWalletClient, http } from "viem";
import { APPKIT_CHAIN } from "./network.ts";

// The Arc chain App Kit settles on, resolved from KERYX_NETWORK (default testnet,
// id 5042002 / 0x4cef52). App Kit validates the id at runtime; we keep the prior
// literal type for the type-checker so all call sites typecheck unchanged. A
// non-testnet network supplies its id via KERYX_APPKIT_CHAIN (see network.ts).
export const ARC_CHAIN = APPKIT_CHAIN as "Arc_Testnet";

/** Build a viem adapter bound to Keryx's Arc RPC (falls back to the chain default RPC). */
export function arcAdapter(privateKey: string, rpcUrl?: string) {
  const transport = http(rpcUrl || undefined);
  return createViemAdapterFromPrivateKey({
    privateKey,
    getPublicClient: ({ chain }) => createPublicClient({ chain, transport }),
    getWalletClient: ({ chain, account }) =>
      createWalletClient({ account, chain, transport }),
  });
}

export type ArcAdapter = ReturnType<typeof arcAdapter>;

/** One AppKit instance is reusable across calls. */
export function createKit(): AppKit {
  return new AppKit();
}

/**
 * Pay an author directly on Arc (P2P USDC Send) — an alternative author-payout rail to the
 * Gateway-batched citation toll. Returns the App Kit send result (carries the tx details).
 */
export function payAuthor(
  kit: AppKit,
  adapter: ArcAdapter,
  to: string,
  amount: string,
  token: "USDC" | "EURC" = "USDC",
) {
  return kit.send({ from: { adapter, chain: ARC_CHAIN }, to, amount, token });
}

/** Bridge USDC into Arc from another chain to fund the paying-agent wallet. */
export function bridgeToArc(
  kit: AppKit,
  fromAdapter: ArcAdapter,
  fromChain: BridgeChain | `${BridgeChain}`,
  toAdapter: ArcAdapter,
  amount: string,
) {
  return kit.bridge({
    from: { adapter: fromAdapter, chain: fromChain },
    to: { adapter: toAdapter, chain: ARC_CHAIN },
    amount,
  });
}

/** Swap an author payout between stablecoins on Arc (USDC <-> EURC). Needs a Circle kit key. */
export function swapOnArc(
  kit: AppKit,
  adapter: ArcAdapter,
  tokenIn: string,
  tokenOut: string,
  amountIn: string,
  kitKey: string,
) {
  return kit.swap({
    from: { adapter, chain: ARC_CHAIN },
    tokenIn,
    tokenOut,
    amountIn,
    config: { kitKey },
  });
}
