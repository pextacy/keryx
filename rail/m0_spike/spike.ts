/**
 * M0 spike — drive ONE test-USDC nanopayment, agent -> author, on Arc.
 *
 * THE GATE (phases.md Phase 1): nothing is built on the rail until this clears
 * end-to-end and the tx is readable on the Arc explorer.
 *
 * Flow (adapted from arc-nanopayments/agent.mts, Apache-2.0 — see NOTICE):
 *   1. spawn an ephemeral agent wallet
 *   2. fund it from BUYER (gas in native USDC + ERC-20 USDC)
 *   3. deposit into the Circle Gateway wallet
 *   4. pay the seller's /cite once via x402 (GatewayClient.pay)
 *   5. print the settlement tx hash + explorer URL
 *
 * Prereqs: `npm run generate-wallets`, fund BUYER at https://faucet.circle.com/,
 * and `npm run seller` running in another terminal. Then: `npm run m0`.
 */
import { GatewayClient } from "@circle-fin/x402-batching/client";
import {
  createPublicClient,
  createWalletClient,
  http,
  erc20Abi,
  parseEther,
  parseUnits,
} from "viem";
import { arcTestnet } from "viem/chains";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";

// Verified constants — see docs/VERIFIED-SIGNATURES.md.
const ARC_TESTNET_USDC = "0x3600000000000000000000000000000000000000" as const;
const ARC_TESTNET_RPC = "https://rpc.testnet.arc.network";

const SELLER_URL = process.env.SELLER_URL ?? "http://localhost:3402/cite";
const DEPOSIT_AMOUNT = process.env.DEPOSIT_AMOUNT ?? "0.05"; // small float for M0
const GAS_FUND_AMOUNT = parseEther("0.01"); // native USDC for gas (18 decimals)

const funderKey = process.env.BUYER_PRIVATE_KEY as `0x${string}` | undefined;
if (!funderKey) {
  console.error("Missing BUYER_PRIVATE_KEY — run `npm run generate-wallets` first.");
  process.exit(1);
}

const funder = privateKeyToAccount(funderKey);
const publicClient = createPublicClient({ chain: arcTestnet, transport: http(ARC_TESTNET_RPC) });
const funderWallet = createWalletClient({
  account: funder,
  chain: arcTestnet,
  transport: http(ARC_TESTNET_RPC),
});

const ephemeralKey = generatePrivateKey();
const ephemeral = privateKeyToAccount(ephemeralKey);
console.log(`[m0] ephemeral agent wallet: ${ephemeral.address}`);
console.log(`[m0] funder (buyer):         ${funder.address}`);

// Sanity: buyer must hold testnet USDC. Fail loud with the faucet link if not.
const funderUsdc = (await publicClient.readContract({
  address: ARC_TESTNET_USDC,
  abi: erc20Abi,
  functionName: "balanceOf",
  args: [funder.address],
})) as bigint;
console.log(`[m0] buyer USDC balance: ${Number(funderUsdc) / 1e6} USDC`);
if (funderUsdc === 0n) {
  console.error(
    `[m0] Buyer has 0 USDC. Fund ${funder.address} at https://faucet.circle.com/ (Arc Testnet) and retry.`,
  );
  process.exit(1);
}

// 1) Gas, then 2) USDC, to the ephemeral wallet (sequential for correct nonce).
console.log("[m0] funding ephemeral wallet for gas...");
const gasTx = await funderWallet.sendTransaction({
  to: ephemeral.address,
  value: GAS_FUND_AMOUNT,
});
await publicClient.waitForTransactionReceipt({ hash: gasTx });
console.log(`[m0]   gas funded (${gasTx.slice(0, 10)}...)`);

const usdcAmount = parseUnits(DEPOSIT_AMOUNT, 6);
console.log(`[m0] transferring ${DEPOSIT_AMOUNT} USDC to ephemeral wallet...`);
const usdcTx = await funderWallet.writeContract({
  address: ARC_TESTNET_USDC,
  abi: erc20Abi,
  functionName: "transfer",
  args: [ephemeral.address, usdcAmount],
});
await publicClient.waitForTransactionReceipt({ hash: usdcTx });
console.log(`[m0]   USDC transferred (${usdcTx.slice(0, 10)}...)`);

// 3) Deposit into the Gateway wallet.
const gateway = new GatewayClient({ chain: "arcTestnet", privateKey: ephemeralKey });
console.log(`[m0] depositing ${DEPOSIT_AMOUNT} USDC into Gateway...`);
const deposit = await gateway.deposit(DEPOSIT_AMOUNT);
console.log(`[m0]   deposit tx: ${deposit.depositTxHash}`);
const balances = await gateway.getBalances();
console.log(`[m0]   gateway available: ${balances.gateway.formattedAvailable}`);

// 4) Pay the seller's /cite ONCE.
console.log(`[m0] paying citation toll -> ${SELLER_URL}`);
const result = await gateway.pay(SELLER_URL, { method: "POST", body: { source_id: "m0-source" } });

// 5) Report.
console.log(`\n[m0] ✅ CITATION SETTLED: ${result.formattedAmount} USDC`);
console.log(`[m0] settlement tx: ${result.transaction}`);
console.log(`[m0] explorer: https://explorer.testnet.arc.network/tx/${result.transaction}`);
console.log(`[m0] M0 gate is GREEN if the tx resolves on the Arc explorer.`);
process.exit(0);
