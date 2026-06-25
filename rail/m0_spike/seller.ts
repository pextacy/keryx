/**
 * M0 seller — the citation-toll endpoint, minimal standalone form.
 *
 * Adapted from arc-nanopayments/lib/x402.ts (Apache-2.0, Circle — see NOTICE):
 * the verify -> settle core is unchanged; we strip Supabase (the upstream's data
 * layer) since chain is canonical, and serve over plain Node HTTP instead of Next.
 * payTo is the AUTHOR wallet, so a cleared payment lands on the author — the M0 goal.
 *
 * This file is the seed of the real rail/cite/ endpoint (Phase 2 / M1).
 */
import { createServer } from "node:http";
import { BatchFacilitatorClient } from "@circle-fin/x402-batching/server";
import { isAddress, parseUnits } from "viem";
// Chain constants resolved from KERYX_NETWORK (default testnet). See network.ts.
import { CAIP2_NETWORK, USDC, GATEWAY_WALLET, txUrl, KERYX_NETWORK } from "./network.ts";

const AUTHOR_ADDRESS = process.env.AUTHOR_ADDRESS as `0x${string}` | undefined;
const PORT = Number(process.env.SELLER_PORT ?? 3402);
const TOLL = process.env.M0_TOLL ?? "0.001";

if (!AUTHOR_ADDRESS) {
  console.error("Missing AUTHOR_ADDRESS — run `npm run generate-wallets` first.");
  process.exit(1);
}

const facilitator = new BatchFacilitatorClient();

// Circle's Gateway facilitator requires each authorization to be valid for at
// least `minValiditySeconds` (7 days on Arc testnet — see /v1/x402/supported).
// The client signs validBefore = now + maxTimeoutSeconds, so maxTimeoutSeconds
// MUST be >= that minimum or verify fails with `authorization_validity_too_short`.
// The @circle-fin/x402-batching library still hardcodes 4 days (345600), which is
// now below the requirement, so we set it explicitly. The extra hour absorbs the
// signing + network latency between the client computing `now` and the facilitator
// re-checking the remaining window.
const GATEWAY_MIN_VALIDITY_SECONDS = 604800; // 7 days, per Circle /supported
const MAX_TIMEOUT_SECONDS = GATEWAY_MIN_VALIDITY_SECONDS + 3600;

// Upper bound on a single citation toll. The amount is client-supplied (query param),
// so without a cap a caller could mint an arbitrarily large signed payment requirement.
// 1 USDC is far above any real sub-cent toll and keeps a fat-finger from draining a payer.
const MAX_TOLL_MICRO_USDC = 1_000_000n; // 1.000000 USDC

/**
 * Parse a client-supplied USDC price into integer micro-USDC, rejecting anything that
 * isn't a clean, in-range positive amount. `parseUnits` is decimal-exact (no float drift
 * like `parseFloat(x) * 1e6`) and throws on non-numeric / >6-decimal input, which we turn
 * into a thrown Error the request handler converts to a 400.
 */
function parseToll(price: string): bigint {
  let micro: bigint;
  try {
    micro = parseUnits(price, 6); // USDC has 6 decimals; throws on garbage / extra precision
  } catch {
    throw new Error(`invalid amount: ${price}`);
  }
  if (micro <= 0n) throw new Error(`amount must be positive: ${price}`);
  if (micro > MAX_TOLL_MICRO_USDC) throw new Error(`amount exceeds max toll: ${price}`);
  return micro;
}

function buildRequirements(payTo: string, amountMicro: bigint) {
  return {
    scheme: "exact" as const,
    network: CAIP2_NETWORK,
    asset: USDC,
    amount: amountMicro.toString(),
    payTo,
    maxTimeoutSeconds: MAX_TIMEOUT_SECONDS,
    extra: {
      name: "GatewayWalletBatched",
      version: "1",
      verifyingContract: GATEWAY_WALLET,
    },
  };
}

const endpoint = "/cite";

const server = createServer(async (req, res) => {
  if (!req.url?.startsWith(endpoint)) {
    res.writeHead(404).end(JSON.stringify({ error: "not found" }));
    return;
  }

  // Per-request payee + toll: the citation pays the *cited author*, which varies per
  // source. Defaults to env (the M0 single-payment case). The verify and settle calls
  // below must use this same requirements object.
  const url = new URL(req.url, `http://${req.headers.host ?? "localhost"}`);
  const payTo = url.searchParams.get("payTo") ?? AUTHOR_ADDRESS!;
  const price = url.searchParams.get("amount") ?? TOLL;

  // Validate client-controlled payee + price before they enter a signed payment
  // requirement. A bad address or a malformed/zero/negative/oversized amount is a 400,
  // not an undefined-behaviour value handed to the facilitator.
  if (!isAddress(payTo)) {
    res.writeHead(400, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "invalid payTo address" }));
    return;
  }
  let amountMicro: bigint;
  try {
    amountMicro = parseToll(price);
  } catch (err) {
    res.writeHead(400, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: err instanceof Error ? err.message : "invalid amount" }));
    return;
  }
  const requirements = buildRequirements(payTo, amountMicro);

  const paymentSignature = req.headers["payment-signature"] as string | undefined;

  // No payment -> 402 with Gateway-batched payment requirements.
  if (!paymentSignature) {
    const paymentRequired = {
      x402Version: 2,
      resource: {
        url: endpoint,
        description: `Citation toll (${price} USDC)`,
        mimeType: "application/json",
      },
      accepts: [requirements],
    };
    console.log(`[seller] 402 Payment Required: ${endpoint}`);
    res.writeHead(402, {
      "Content-Type": "application/json",
      "PAYMENT-REQUIRED": Buffer.from(JSON.stringify(paymentRequired)).toString("base64"),
    });
    res.end(JSON.stringify({}));
    return;
  }

  // Payment present -> verify + settle via Circle Gateway.
  try {
    const paymentPayload = JSON.parse(
      Buffer.from(paymentSignature, "base64").toString("utf-8"),
    );

    const verify = await facilitator.verify(paymentPayload, requirements);
    if (!verify.isValid) {
      console.error(`[seller] verify failed: ${verify.invalidReason}`);
      res.writeHead(402, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "verification failed", reason: verify.invalidReason }));
      return;
    }

    const settle = await facilitator.settle(paymentPayload, requirements);
    if (!settle.success) {
      console.error(`[seller] settle failed: ${settle.errorReason}`);
      res.writeHead(402, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "settlement failed", reason: settle.errorReason }));
      return;
    }

    const payer = settle.payer ?? verify.payer ?? "unknown";
    console.log(
      `[seller] SETTLED ${price} USDC from ${payer} -> author ${payTo}`,
    );
    console.log(`[seller] tx: ${settle.transaction}`);
    console.log(`[seller] explorer: ${txUrl(settle.transaction)}`);

    const paymentResponse = Buffer.from(
      JSON.stringify({
        success: true,
        transaction: settle.transaction,
        network: requirements.network,
        payer,
      }),
    ).toString("base64");

    res.writeHead(200, { "Content-Type": "application/json", "PAYMENT-RESPONSE": paymentResponse });
    res.end(JSON.stringify({ cited: true, source_id: "m0-source", tx_hash: settle.transaction }));
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`[seller] error: ${message}`);
    res.writeHead(500, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "processing error", message }));
  }
});

server.listen(PORT, () => {
  console.log(`[seller] M0 citation-toll seller on http://localhost:${PORT}${endpoint}`);
  console.log(`[seller] network=${KERYX_NETWORK} (${CAIP2_NETWORK}), payTo author ${AUTHOR_ADDRESS}, toll ${TOLL} USDC`);
});
