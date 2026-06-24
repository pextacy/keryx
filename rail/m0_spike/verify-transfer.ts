/**
 * Verify an M0 citation settlement actually landed on Arc.
 *
 * The Gateway batched model: pay() returns a transfer UUID, the cited author
 * receives into their *Gateway balance* (attested, backed by on-chain deposits),
 * and the batch mints on-chain through statuses received -> batched -> confirmed
 * -> completed. This script proves it: it looks up the transfer by id and prints
 * the author's Gateway balance.
 *
 * Usage: node --experimental-transform-types --env-file=.env verify-transfer.ts <transferId>
 */
import { GatewayClient } from "@circle-fin/x402-batching/client";
import { GATEWAY_CLIENT_CHAIN } from "./network.ts";

const transferId = process.argv[2];
const buyerKey = process.env.BUYER_PRIVATE_KEY as `0x${string}`;
const authorKey = process.env.AUTHOR_PRIVATE_KEY as `0x${string}`;

const buyer = new GatewayClient({ chain: GATEWAY_CLIENT_CHAIN, privateKey: buyerKey });

if (transferId) {
  console.log(`[verify] looking up transfer ${transferId}...`);
  const t = await buyer.getTransferById(transferId);
  console.log(`[verify] status:        ${t.status}`);
  console.log(`[verify] from:          ${t.fromAddress}`);
  console.log(`[verify] to (author):   ${t.toAddress}`);
  console.log(`[verify] amount:        ${t.amount} USDC`);
  console.log(`[verify] sendingNet:    ${t.sendingNetwork}`);
  console.log(`[verify] recipientNet:  ${t.recipientNetwork}`);
  for (const k of ["mintTxHash", "txHash", "transactionHash", "transaction"]) {
    if (t[k]) console.log(`[verify] ${k}: ${t[k]}`);
  }
}

if (authorKey) {
  const author = new GatewayClient({ chain: GATEWAY_CLIENT_CHAIN, privateKey: authorKey });
  const bal = await author.getBalances();
  console.log(`\n[verify] AUTHOR Gateway balance: ${bal.gateway.formattedTotal} total / ${bal.gateway.formattedAvailable} available`);
  console.log(`[verify] AUTHOR wallet (EOA) balance: ${bal.wallet.formatted}`);
}
