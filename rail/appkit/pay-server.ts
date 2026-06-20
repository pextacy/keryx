/**
 * App Kit pay server — author payouts over App Kit Send (P2P USDC on Arc).
 *
 * An alternative to the Gateway-batched citation toll (rail/m0_spike/payer.ts): for one-off
 * payouts the agent can POST here and the App Kit Send capability transfers USDC directly to
 * the author wallet. Same spirit as the payer bridge, simpler settlement.
 *
 *   POST /pay  { to, amount, token? }  ->  { ok, result }
 *
 * Prereqs: funded BUYER_PRIVATE_KEY. Run: npm run pay.
 */
import { createServer } from "node:http";
import { arcAdapter, createKit, payAuthor } from "./appkit.ts";

const PORT = Number(process.env.PAY_PORT ?? 3404);
const RPC_URL = process.env.ARC_RPC_URL ?? "";
const buyerKey = process.env.BUYER_PRIVATE_KEY;
if (!buyerKey) {
  console.error("Missing BUYER_PRIVATE_KEY — generate and fund a wallet first.");
  process.exit(1);
}

const kit = createKit();
const adapter = arcAdapter(buyerKey, RPC_URL);

// JSON.stringify replacer: serialize bigints (App Kit results can carry them).
const safe = (v: unknown) =>
  JSON.stringify(v, (_k, val) => (typeof val === "bigint" ? val.toString() : val));

interface PayBody {
  to?: string;
  amount?: string;
  token?: "USDC" | "EURC";
}

const server = createServer((req, res) => {
  if (req.method !== "POST" || req.url !== "/pay") {
    res.writeHead(404).end(safe({ error: "POST /pay" }));
    return;
  }
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", async () => {
    try {
      const body = JSON.parse(raw || "{}") as PayBody;
      if (!body.to || !body.amount) throw new Error("to and amount are required");
      const result = await payAuthor(kit, adapter, body.to, body.amount, body.token ?? "USDC");
      res.writeHead(200, { "content-type": "application/json" }).end(safe({ ok: true, result }));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      res.writeHead(400, { "content-type": "application/json" }).end(safe({ ok: false, error: message }));
    }
  });
});

server.listen(PORT, () => console.log(`[appkit] pay server on :${PORT} (POST /pay)`));
