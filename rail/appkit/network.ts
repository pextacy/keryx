/**
 * Network selection for the App Kit rail — mirrors rail/m0_spike/network.ts and
 * shared/network.py. App Kit identifies chains by its own enums/ids (e.g.
 * "Arc_Testnet"), so this module resolves those from KERYX_NETWORK rather than
 * hardcoding them across appkit.ts / earn.ts.
 *
 * Keryx is testnet-only (Arc Testnet). The App Kit chain ids can still be
 * overridden via env (KERYX_APPKIT_CHAIN / *_EARN_CHAIN).
 */
import { EarnChain } from "@circle-fin/app-kit";

const NETWORK = (process.env.KERYX_NETWORK ?? "testnet").toLowerCase();

interface AppkitPreset {
  chain?: string; // send/bridge/swap chain id
  earn?: keyof typeof EarnChain; // EarnChain enum key
}

const PRESETS: Record<string, AppkitPreset> = {
  testnet: { chain: "Arc_Testnet", earn: "Arc_Testnet" },
};

if (!(NETWORK in PRESETS)) {
  throw new Error(
    `unknown KERYX_NETWORK="${NETWORK}"; expected one of ${Object.keys(PRESETS).join(", ")} ` +
      `(Keryx is testnet-only)`,
  );
}

const preset = PRESETS[NETWORK];

function need(envVar: string, presetVal: string | undefined): string {
  const env = process.env[envVar];
  if (env !== undefined && env !== "") return env;
  if (presetVal !== undefined) return presetVal;
  throw new Error(
    `App Kit network="${NETWORK}" has no value for ${envVar}. Set ${envVar} to the ` +
      `App Kit chain id (Keryx is testnet-only).`,
  );
}

export const KERYX_NETWORK = NETWORK;

// App Kit's send/bridge/swap chain id. Typed loosely (string) and cast at the call
// sites; the SDK validates the id at runtime.
export const APPKIT_CHAIN = need("KERYX_APPKIT_CHAIN", preset.chain);

// App Kit's Earn vault chain — an EarnChain enum member.
const earnKey = (process.env.KERYX_APPKIT_EARN_CHAIN ?? preset.earn) as
  | keyof typeof EarnChain
  | undefined;
if (earnKey === undefined || !(earnKey in EarnChain)) {
  throw new Error(
    `App Kit network="${NETWORK}" has no valid EarnChain. Set KERYX_APPKIT_EARN_CHAIN ` +
      `to a valid EarnChain key (e.g. one of: ${Object.keys(EarnChain).join(", ")}).`,
  );
}
export const APPKIT_EARN_CHAIN = EarnChain[earnKey];
