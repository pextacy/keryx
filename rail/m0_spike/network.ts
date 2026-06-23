/**
 * Network registry for the TS rail — the single source of truth for chain
 * constants on this side, mirroring shared/network.py on the Python side.
 *
 * Select with KERYX_NETWORK (default "testnet"). Every constant can be overridden
 * by its KERYX_* env var — the SAME vars the Python config reads — so the two
 * sides never drift. The hackathon is testnet-only; the "mainnet" preset is
 * deliberately empty, so selecting it without supplying verified Circle/Arc
 * mainnet values throws instead of settling real funds against a placeholder.
 */
import { defineChain } from "viem";
import { arcTestnet } from "viem/chains";
import type { Chain } from "viem";
import type { GatewayClient } from "@circle-fin/x402-batching/client";

// The Circle Gateway SDK accepts only its known chain ids (a string-literal union).
type GatewayChain = NonNullable<ConstructorParameters<typeof GatewayClient>[0]>["chain"];

type Maybe = string | undefined;

interface Preset {
  chainId?: number;
  rpcUrl?: string;
  usdc?: string;
  gatewayWallet?: string;
  caip2Network?: string;
  explorer?: string;
  gatewayClientChain?: string; // @circle-fin/x402-batching GatewayClient `chain`
  appkitChain?: string; // @circle-fin/app-kit chain id
}

const PRESETS: Record<string, Preset> = {
  // Arc Testnet — verified vs arc-nanopayments + live RPC (docs/VERIFIED-SIGNATURES.md).
  testnet: {
    chainId: 5042002, // 0x4cef52
    rpcUrl: "https://rpc.testnet.arc.network",
    usdc: "0x3600000000000000000000000000000000000000",
    gatewayWallet: "0x0077777d7EBA4688BDeF3E311b846F25870A19B9",
    caip2Network: "eip155:5042002",
    explorer: "https://testnet.arcscan.app",
    gatewayClientChain: "arcTestnet",
    appkitChain: "Arc_Testnet",
  },
  // Arc Mainnet — DELIBERATELY EMPTY. Provide every value via KERYX_* env vars
  // (verified against Circle/Arc mainnet docs) before selecting this network.
  mainnet: {},
};

const NETWORK = (process.env.KERYX_NETWORK ?? "testnet").toLowerCase();

if (!(NETWORK in PRESETS)) {
  throw new Error(
    `unknown KERYX_NETWORK="${NETWORK}"; expected one of ${Object.keys(PRESETS).join(", ")}`,
  );
}

const preset = PRESETS[NETWORK];

/** Resolve a constant: explicit env var wins, then the network preset, else throw. */
function need<T extends string | number>(
  envVar: string,
  presetVal: T | undefined,
  parse: (s: string) => T = (s) => s as T,
): T {
  const env = process.env[envVar];
  if (env !== undefined && env !== "") return parse(env);
  if (presetVal !== undefined) return presetVal;
  throw new Error(
    `network="${NETWORK}" has no verified value for ${envVar}. Set ${envVar} ` +
      `(verified against Circle/Arc mainnet docs) before using this network. ` +
      `The hackathon is testnet-only.`,
  );
}

export const KERYX_NETWORK = NETWORK;
export const CHAIN_ID = need("KERYX_ARC_CHAIN_ID", preset.chainId, (s) => Number(s));
export const RPC_URL = need("KERYX_RPC_URL", preset.rpcUrl);
export const USDC = need("KERYX_USDC_ADDRESS", preset.usdc) as `0x${string}`;
export const GATEWAY_WALLET = need("KERYX_GATEWAY_WALLET", preset.gatewayWallet) as `0x${string}`;
export const CAIP2_NETWORK = need("KERYX_CAIP2_NETWORK", preset.caip2Network);
export const EXPLORER = need("KERYX_EXPLORER_URL", preset.explorer);
export const GATEWAY_CLIENT_CHAIN = need(
  "KERYX_GATEWAY_CLIENT_CHAIN",
  preset.gatewayClientChain,
) as GatewayChain;
export const APPKIT_CHAIN = need("KERYX_APPKIT_CHAIN", preset.appkitChain);

/** Explorer tx URL for a settlement hash. */
export function txUrl(hash: Maybe): string {
  return `${EXPLORER}/tx/${hash ?? ""}`;
}

/** The viem Chain for the selected network: testnet uses viem's canonical
 * `arcTestnet`; any other network is built from the resolved constants. */
export function viemChain(): Chain {
  if (NETWORK === "testnet") return arcTestnet;
  return defineChain({
    id: CHAIN_ID,
    name: `Arc (${NETWORK})`,
    nativeCurrency: { name: "USD Coin", symbol: "USDC", decimals: 18 },
    rpcUrls: { default: { http: [RPC_URL] } },
    blockExplorers: { default: { name: "Arcscan", url: EXPLORER } },
  });
}
