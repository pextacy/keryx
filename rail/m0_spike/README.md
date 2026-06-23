# M0 spike — the rail gate

**Goal (phases.md Phase 1):** one test-USDC nanopayment clears **agent → author** on
Arc, end-to-end, with the tx readable on the explorer. Nothing is built on the rail
until this is green.

This spike is the canonical path assembled from `@circle-fin/x402-batching` (Circle,
Apache-2.0) — no Supabase, no Next.js. `seller.ts` is the seed of the real
`rail/cite/` endpoint. Constants verified in [`../../docs/VERIFIED-SIGNATURES.md`](../../docs/VERIFIED-SIGNATURES.md).

## What's already verified (no funds needed)

- ✅ Builds + typechecks against the real SDK (`tsc --noEmit`, exit 0).
- ✅ Seller boots and returns a correct x402 `402` with a Gateway-batched
  `PAYMENT-REQUIRED` (network `eip155:5042002`, USDC asset, `payTo` author,
  `extra.verifyingContract` = Gateway wallet).
- ✅ Arc testnet RPC reachable (`eth_chainId` = `0x4cef52` = 5042002).

## Run it (needs testnet USDC — your action)

```bash
cd rail/m0_spike
npm install

# 1. Generate fresh AUTHOR (payee) + BUYER (funder) wallets -> writes .env
npm run generate-wallets

# 2. Fund the BUYER address with Arc testnet USDC (the only manual step).
#    Option A — web faucet:  https://faucet.circle.com/  (select Arc Testnet)
#    Option B — Circle CLI (needs an interactive email-OTP login):
#        npx @circle-fin/cli wallet login
#        npx @circle-fin/cli wallet fund --address <BUYER_ADDRESS> --chain ARC-TESTNET --token usdc
#    Confirm balance:
#        npx @circle-fin/cli wallet balance --address <BUYER_ADDRESS> --chain ARC-TESTNET

# 3. Terminal A — start the citation-toll seller (payTo = author):
npm run seller

# 4. Terminal B — drive ONE citation payment:
npm run m0
```

`npm run m0` will: spawn an ephemeral agent wallet, fund it from BUYER (gas + USDC),
deposit into the Gateway wallet, pay the seller's `/cite` once via x402, and print:

```
[m0] ✅ CITATION SETTLED: 0.001 USDC
[m0] settlement tx: 0x...
[m0] explorer: https://testnet.arcscan.app/tx/0x...
```

**M0 is GREEN when that tx resolves on the Arc explorer.** Paste the tx hash into
`docs/phases.md` Phase 1 DoD.

## Notes

- The buyer needs enough USDC for gas (native USDC, 18 decimals) + the deposit. The
  spike funds the ephemeral wallet with `DEPOSIT_AMOUNT` (default 0.05) and 0.01 for gas.
- If the buyer has 0 USDC the spike exits early with the faucet link.
