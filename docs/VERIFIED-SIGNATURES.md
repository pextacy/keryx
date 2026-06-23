# Verified Arc / x402 / Gateway signatures

Phase 1 (M0) mandates: **verify every signature against source + live docs at build
time — never trust signatures reproduced from planning files.** This file records
what was verified, from where, and when, so the rest of the build trusts source.

**Verified 2026-06-19** against `vendor/arc-nanopayments` (`circlefin/arc-nanopayments`,
Apache-2.0, commit pinned in `vendor/`) — files `lib/x402.ts`, `agent.mts`,
`generate-wallets.mts` — and the live Arc testnet RPC.

## Network-parametric (not hardcoded)

These constants are **not hardcoded in business logic** — they are a named-network
preset resolved at runtime from `KERYX_NETWORK` (default `testnet`). The single
source of truth is `shared/network.py` (Python) and `rail/m0_spike/network.ts` +
`rail/appkit/network.ts` (TS); both read the same `KERYX_*` env vars so the two
sides never drift. The `testnet` preset is the verified table below. The `mainnet`
preset is deliberately empty: selecting it requires every constant to be supplied
(verified vs Circle/Arc **mainnet** docs) via env, or startup fails loud rather
than reusing a testnet address. **The hackathon is testnet-only** — mainnet support
is structural readiness, not a green-lit mainnet deployment.

## Arc Testnet constants

| Thing | Value | Source |
| --- | --- | --- |
| Chain id | `0x4cef52` = **5042002** | live RPC `eth_chainId` ✓ + `eip155:5042002` in `lib/x402.ts` |
| CAIP-2 network | `eip155:5042002` | `lib/x402.ts` `ARC_TESTNET_NETWORK` |
| RPC URL | `https://rpc.testnet.arc.network` | `agent.mts` `ARC_TESTNET_RPC` (reachable ✓) |
| USDC (ERC-20, 6 dp) | `0x3600000000000000000000000000000000000000` | `lib/x402.ts` / `agent.mts` |
| Gateway batching contract | `0x0077777d7EBA4688BDeF3E311b846F25870A19B9` | `lib/x402.ts` `ARC_TESTNET_GATEWAY_WALLET` |
| Gas token | **native USDC, 18 decimals** (`parseEther` for gas; `parseUnits(_,6)` for ERC-20 value) | `agent.mts` |
| viem chain | `arcTestnet` from `viem/chains`; GatewayClient `chain: "arcTestnet"` | `agent.mts` |
| Faucet | `https://faucet.circle.com/` (Arc Testnet) | `generate-wallets.mts` |
| Explorer | `https://testnet.arcscan.app` (verify path on first tx) | Arc docs |

## SDK — `@circle-fin/x402-batching`

This is the canonical Circle implementation of x402 + Gateway batching. **We use it as
is** ("assemble, don't author"). There is no Python equivalent — see DECISIONS.md on
the rail language; M0 runs in TypeScript regardless.

**Server (seller):** `import { BatchFacilitatorClient } from "@circle-fin/x402-batching/server"`
- `new BatchFacilitatorClient()`
- `await facilitator.verify(paymentPayload, requirements)` → `{ isValid, invalidReason?, payer? }`
- `await facilitator.settle(paymentPayload, requirements)` → `{ success, transaction?, payer?, errorReason? }`
  - `settle().transaction` is the on-chain settlement tx hash.

**Client (paying agent):** `import { GatewayClient } from "@circle-fin/x402-batching/client"`
- `new GatewayClient({ chain: "arcTestnet", privateKey })`
- `await gateway.deposit(amountStr)` → `{ depositTxHash }`
- `await gateway.getBalances()` → `{ wallet: { balance, ... }, gateway: { available, formattedAvailable } }`
- `await gateway.pay(url, { method, body? })` → `{ formattedAmount, ... }` — runs the full
  x402 dance (hits the 402, signs the Gateway-batched authorization, retries, returns settlement).

## x402 wire shape (HTTP)

**402 response** (seller, no payment): header `PAYMENT-REQUIRED` = base64(JSON):
```json
{ "x402Version": 2,
  "resource": { "url": "<endpoint>", "description": "...", "mimeType": "application/json" },
  "accepts": [ <PaymentRequirements> ] }
```

**PaymentRequirements** (the `extra` block is what makes it Gateway-batched):
```json
{ "scheme": "exact",
  "network": "eip155:5042002",
  "asset": "0x3600000000000000000000000000000000000000",
  "amount": "<atomic USDC, 6dp, as string>",
  "payTo": "<seller/author address>",
  "maxTimeoutSeconds": 608400,
  "extra": { "name": "GatewayWalletBatched", "version": "1",
             "verifyingContract": "0x0077777d7EBA4688BDeF3E311b846F25870A19B9" } }
```
⚠️ **`maxTimeoutSeconds` must be ≥ Circle's `minValiditySeconds`** (currently **604800** = 7d
on Arc testnet — query `GET https://gateway-api-testnet.circle.com/v1/x402/supported`). The
client signs `validBefore = now + maxTimeoutSeconds`; the facilitator rejects anything whose
remaining validity is under the minimum with `authorization_validity_too_short`. The
`@circle-fin/x402-batching` SDK still defaults this to `345600` (4d) — below the requirement —
so the seller sets it explicitly to `604800 + 3600` (7d + 1h latency buffer). Verified live on
2026-06-23 by the first cleared M0 settlement.

**Retry request** (client): header `payment-signature` = base64(JSON PaymentPayload):
```json
{ "x402Version": <n>, "resource": {...}?, "accepted": {...}?,
  "payload": { ... }, "extensions": { ... }? }
```
The EIP-3009-style authorization is produced inside the SDK from the above
`extra` (EIP-712 domain: name `GatewayWalletBatched`, version `1`, verifyingContract =
Gateway wallet). We do not hand-roll the signature — the SDK owns it.

**Success response** (seller): header `PAYMENT-RESPONSE` = base64(JSON):
```json
{ "success": true, "transaction": "<tx hash>", "network": "eip155:5042002", "payer": "0x..." }
```

## Amount conversion

`atomic = Math.round(parseFloat(dollars) * 1_000_000)` (USDC has 6 decimals). Our floor
`$0.000001` = `1` atomic unit; toll `$0.001–$0.01` = `1_000–10_000` atomic units.

## Our delta (for `/cite` in Phase 2)

`lib/x402.ts`'s `withGateway()` records to **Supabase** — we strip that and write to
**Neon** `citations_index` instead (chain stays canonical). The verify→settle core and
all constants above carry over unchanged.
