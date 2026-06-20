# Keryx Rail — App Kit capabilities

A higher-level complement to the x402 + Gateway settlement path (`rail/m0_spike`), using
Circle's [App Kit](https://docs.arc.io/app-kit) for **Send / Bridge / Swap** of USDC on Arc
behind one type-safe interface. No new protocol wiring per use case.

## Why this exists for Keryx

| Capability | Keryx use |
| --- | --- |
| `send()` | Pay an author directly (P2P USDC) — an alternative to the Gateway-batched citation toll for one-off payouts. |
| `bridge()` | Fund the paying-agent wallet on Arc from another chain. |
| `swap()` | Convert an author payout between stablecoins on Arc (USDC ↔ EURC). Needs a Circle kit key. |

The viem adapter is bound to Keryx's configured Arc RPC (`ARC_RPC_URL`, mirrors
`KERYX_RPC_URL`), so it hits the same node as the rest of the rail. `arcTestnet` (chain id
`5042002` / `0x4cef52`) is the only settlement chain.

## Files

- `appkit.ts` — the library: `arcAdapter()`, `createKit()`, `payAuthor()`, `bridgeToArc()`, `swapOnArc()`.
- `pay-server.ts` — `POST /pay { to, amount, token? }` author-payout HTTP service (App Kit Send).
- `demo.ts` — runnable config check / one-off payout.

## Run

```bash
cp .env.example .env        # set BUYER_PRIVATE_KEY (funded), ARC_RPC_URL
npm install
npm run typecheck           # tsc --noEmit (verified)
npm run demo                # config only, no tx
npm run demo -- 0xAuthor... 1.00   # send 1.00 USDC to an author
npm run pay                 # start the POST /pay server (default :3404)
```

```bash
# Example payout via the server:
curl -s localhost:3404/pay -d '{"to":"0xAuthorWallet","amount":"0.50"}'
```

Import is side-effect free; nothing touches the network until a function is called with a
funded key. Testnet only — no mainnet, no real funds.
