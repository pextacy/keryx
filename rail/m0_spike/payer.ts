/**
 * Payer bridge — turns the frozen Rail contract into real x402 settlements.
 *
 * The Python agent (the moat) settles by POSTing CitationIntents here; this service
 * holds the funded paying-agent wallet, manages the Gateway deposit, and pays each
 * cited author via GatewayClient.pay() against the seller's /cite (payTo = author).
 * Returns one Receipt per intent, in order — the same shape MockRail returns, so the
 * Python side swaps MockRail -> HttpRail with no other change (Phase 3 / M2).
 *
 * POST /settle  { intents: [{ source_id, author_wallet, amount }] }
 *            -> { receipts: [{ source_id, tx_hash, status }] }
 *
 * Prereqs: funded BUYER_PRIVATE_KEY + a running seller (SELLER_URL). Run: npm run payer.
 */
import { createServer } from "node:http";
import { GatewayClient } from "@circle-fin/x402-batching/client";

const SELLER_URL = process.env.SELLER_URL ?? "http://localhost:3402/cite";
const PORT = Number(process.env.PAYER_PORT ?? 3403);
const DEPOSIT_AMOUNT = process.env.DEPOSIT_AMOUNT ?? "0.5";
const REDEPOSIT_THRESHOLD = 500_000n; // 0.5 USDC atomic

const buyerKey = process.env.BUYER_PRIVATE_KEY as `0x${string}` | undefined;
if (!buyerKey) {
  console.error("Missing BUYER_PRIVATE_KEY — run `npm run generate-wallets` and fund it.");
  process.exit(1);
}

const gateway = new GatewayClient({ chain: "arcTestnet", privateKey: buyerKey });

interface Intent {
  source_id: string;
  author_wallet: string;
  amount: string;
}
interface Receipt {
  source_id: string;
  tx_hash: string | null;
  status: "settled" | "failed";
}

async function ensureBalance(): Promise<void> {
  const balances = await gateway.getBalances();
  if (balances.gateway.available < REDEPOSIT_THRESHOLD) {
    console.log(`[payer] gateway low (${balances.gateway.formattedAvailable}), depositing...`);
    await gateway.deposit(DEPOSIT_AMOUNT);
  }
}

async function settleOne(intent: Intent): Promise<Receipt> {
  const url = `${SELLER_URL}?payTo=${intent.author_wallet}&amount=${intent.amount}`;
  try {
    const result = await gateway.pay(url, {
      method: "POST",
      body: { source_id: intent.source_id },
    });
    return { source_id: intent.source_id, tx_hash: result.transaction, status: "settled" };
  } catch (err) {
    console.error(`[payer] settle failed for ${intent.source_id}: ${(err as Error).message}`);
    return { source_id: intent.source_id, tx_hash: null, status: "failed" };
  }
}

function readBody(req: import("node:http").IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (c) => (data += c));
    req.on("end", () => resolve(data));
    req.on("error", reject);
  });
}

const server = createServer(async (req, res) => {
  if (req.method !== "POST" || !req.url?.startsWith("/settle")) {
    res.writeHead(404).end(JSON.stringify({ error: "not found" }));
    return;
  }
  try {
    const { intents } = JSON.parse((await readBody(req)) || "{}") as { intents?: Intent[] };
    if (!intents?.length) {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ receipts: [] }));
      return;
    }
    await ensureBalance();
    // Sequential keeps deposit/nonce ordering simple; batch volume tuning comes later.
    const receipts: Receipt[] = [];
    for (const intent of intents) receipts.push(await settleOne(intent));
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ receipts }));
  } catch (err) {
    res.writeHead(500, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: (err as Error).message }));
  }
});

server.listen(PORT, () => {
  console.log(`[payer] rail bridge on http://localhost:${PORT}/settle -> seller ${SELLER_URL}`);
});
