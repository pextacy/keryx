/**
 * App Kit demo — build the Arc adapter + kit, and optionally send a payout.
 *
 *   npm run demo                      # config only (no tx)
 *   npm run demo -- <to> <amount>     # send <amount> USDC to <to> on Arc (needs funds)
 *
 * Safe by default: with no args it only prints the wired config and exits.
 */
import { arcAdapter, ARC_CHAIN, createKit, payAuthor } from "./appkit.ts";

const RPC_URL = process.env.ARC_RPC_URL ?? "(viem default)";
const buyerKey = process.env.BUYER_PRIVATE_KEY;
if (!buyerKey) {
  console.error("Missing BUYER_PRIVATE_KEY.");
  process.exit(1);
}

const [to, amount] = process.argv.slice(2);
const kit = createKit();
const adapter = arcAdapter(buyerKey, process.env.ARC_RPC_URL);

console.log(`[appkit] chain=${ARC_CHAIN} rpc=${RPC_URL}`);

if (!to || !amount) {
  console.log("[appkit] config OK. Pass <to> <amount> to send a USDC payout.");
  process.exit(0);
}

const result = await payAuthor(kit, adapter, to, amount);
console.log(
  "[appkit] sent:",
  JSON.stringify(result, (_k, v) => (typeof v === "bigint" ? v.toString() : v)),
);
