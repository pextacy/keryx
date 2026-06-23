/**
 * App Kit Earn — yield on idle treasury for the paying agent.
 *
 * Keryx use: park unsettled citation/job budget in a vault to earn yield, then withdraw to
 * settle. Reuses the Arc adapter + kit from appkit.ts.
 */
import { AppKit } from "@circle-fin/app-kit";
import { type ArcAdapter } from "./appkit.ts";
import { APPKIT_EARN_CHAIN } from "./network.ts";

// Earn vault chain, resolved from KERYX_NETWORK (default testnet). See network.ts.
export const ARC_EARN = APPKIT_EARN_CHAIN;

/** Read info for specific Arc vaults (chain + vaultAddress pairs). */
export function getVaultsInfo(kit: AppKit, vaultAddresses: string[]) {
  return kit.earn.getVaults({
    vaults: vaultAddresses.map((vaultAddress) => ({ chain: ARC_EARN, vaultAddress })),
  });
}

/** Deposit USDC into a vault to start earning. */
export function depositToVault(
  kit: AppKit,
  adapter: ArcAdapter,
  vaultAddress: string,
  amount: string,
) {
  return kit.earn.deposit({
    from: { adapter, chain: ARC_EARN },
    vaultAddress,
    amount,
  });
}

/** Withdraw USDC from a vault back to spendable funds. */
export function withdrawFromVault(
  kit: AppKit,
  adapter: ArcAdapter,
  vaultAddress: string,
  amount: string,
) {
  return kit.earn.withdraw({
    from: { adapter, chain: ARC_EARN },
    vaultAddress,
    amount,
  });
}

/** Read the agent's position in a vault. */
export function getEarnPosition(
  kit: AppKit,
  adapter: ArcAdapter,
  vaultAddress: string,
) {
  return kit.earn.getPosition({
    from: { adapter, chain: ARC_EARN },
    vaultAddress,
  });
}
