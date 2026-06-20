/**
 * Keryx rail capabilities server — one HTTP front door to every Arc/Circle App Kit
 * capability: Send, Bridge, Swap, Unified Balance, Earn, and pre-flight Estimates.
 *
 *   POST /send                 { to, amount, token? }
 *   POST /bridge               { fromChain, amount }
 *   POST /swap                 { tokenIn, tokenOut, amountIn, kitKey? }
 *   POST /unified/deposit      { fromChain, amount, token? }
 *   POST /unified/spend        { to, amount, token? }
 *   GET  /unified/balance      ?account=0x..&token=USDC
 *   POST /earn/deposit         { vault, amount }
 *   POST /earn/withdraw        { vault, amount }
 *   GET  /earn/vaults
 *   POST /estimate/bridge      { fromChain, amount }
 *   POST /estimate/swap        { tokenIn, tokenOut, amountIn, kitKey? }
 *
 * Gated by BUYER_PRIVATE_KEY; bigint-safe JSON; errors -> 400. Run: npm run capabilities.
 */
import { createServer, type IncomingMessage } from "node:http";
import { BridgeChain, UnifiedBalanceChain } from "@circle-fin/app-kit";
import { arcAdapter, bridgeToArc, createKit, payAuthor, swapOnArc } from "./appkit.ts";
import { depositToBalance, getUnifiedBalance, spendFromBalance } from "./unified-balance.ts";
import { depositToVault, getVaultsInfo, withdrawFromVault } from "./earn.ts";
import { quoteBridge, quoteSwap } from "./estimate.ts";

const PORT = Number(process.env.CAPABILITIES_PORT ?? 3405);
const RPC_URL = process.env.ARC_RPC_URL ?? "";
const KIT_KEY = process.env.KIT_KEY ?? "";
const buyerKey = process.env.BUYER_PRIVATE_KEY;
if (!buyerKey) {
  console.error("Missing BUYER_PRIVATE_KEY.");
  process.exit(1);
}

const kit = createKit();
const adapter = arcAdapter(buyerKey, RPC_URL);

const safe = (v: unknown) =>
  JSON.stringify(v, (_k, val) => (typeof val === "bigint" ? val.toString() : val));

function readJson(req: IncomingMessage): Promise<Record<string, string>> {
  return new Promise((resolve, reject) => {
    let raw = "";
    req.on("data", (c) => (raw += c));
    req.on("end", () => {
      try {
        resolve(raw ? JSON.parse(raw) : {});
      } catch (err) {
        reject(err instanceof Error ? err : new Error(String(err)));
      }
    });
    req.on("error", reject);
  });
}

type Handler = (
  body: Record<string, string>,
  query: URLSearchParams,
) => Promise<unknown>;

const routes: Record<string, Handler> = {
  "POST /send": (b) => payAuthor(kit, adapter, b.to, b.amount, (b.token as "USDC" | "EURC") ?? "USDC"),
  "POST /bridge": (b) => bridgeToArc(kit, adapter, b.fromChain as BridgeChain, adapter, b.amount),
  "POST /swap": (b) => swapOnArc(kit, adapter, b.tokenIn, b.tokenOut, b.amountIn, b.kitKey ?? KIT_KEY),
  "POST /unified/deposit": (b) =>
    depositToBalance(kit, adapter, b.fromChain as UnifiedBalanceChain, b.amount),
  "POST /unified/spend": (b) => spendFromBalance(kit, adapter, adapter, b.to, b.amount),
  "GET /unified/balance": () => getUnifiedBalance(kit, adapter),
  "POST /earn/deposit": (b) => depositToVault(kit, adapter, b.vault, b.amount),
  "POST /earn/withdraw": (b) => withdrawFromVault(kit, adapter, b.vault, b.amount),
  "GET /earn/vaults": (_b, q) => getVaultsInfo(kit, (q.get("vaults") ?? "").split(",").filter(Boolean)),
  "POST /estimate/bridge": (b) => quoteBridge(kit, adapter, b.fromChain as BridgeChain, adapter, b.amount),
  "POST /estimate/swap": (b) => quoteSwap(kit, adapter, b.tokenIn, b.tokenOut, b.amountIn, b.kitKey ?? KIT_KEY),
};

const server = createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", `http://localhost:${PORT}`);
  const handler = routes[`${req.method} ${url.pathname}`];
  if (!handler) {
    res.writeHead(404, { "content-type": "application/json" }).end(safe({ error: "unknown route" }));
    return;
  }
  try {
    const body = req.method === "POST" ? await readJson(req) : {};
    const result = await handler(body, url.searchParams);
    res.writeHead(200, { "content-type": "application/json" }).end(safe({ ok: true, result }));
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    res.writeHead(400, { "content-type": "application/json" }).end(safe({ ok: false, error: message }));
  }
});

server.listen(PORT, () => console.log(`[appkit] capabilities server on :${PORT}`));
