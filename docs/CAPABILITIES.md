# Keryx capabilities — endpoint reference

Every nanopayment primitive the agent exposes, with copy-paste `curl`. The agent runs at
`http://127.0.0.1:8000` (`make agent` or `uvicorn agent.main:app`). All amounts are test-USDC
strings (6-dp); every settling endpoint clears through the active rail (MockRail by default,
the real x402+Gateway `HttpRail` when `KERYX_RAIL=http`). A live UI for all of these is at
`/capabilities` in the web app (`cd web && pnpm dev`).

Splits are **exact**: every payout/match sums to the input down to the micro-USDC, with no
dust and never overpaying. On-chain read endpoints are **opt-in** and return `{"enabled": false}`
until their `KERYX_*_ENABLED` flag is set.

---

## Royalty split — pay every credited contributor (PA 04)

`POST /payout` — split one payment across contributors in the proportions the attribution
graph records.

```bash
curl -s localhost:8000/payout -H 'content-type: application/json' -d '{
  "amount": "0.01",
  "contributors": [
    {"wallet": "0xaaaa...aaaa", "share": "60"},
    {"wallet": "0xbbbb...bbbb", "share": "30"},
    {"wallet": "0xcccc...cccc", "share": "10"}
  ]
}'
# -> {"amount":"0.01","recipients":[{"wallet":...,"amount":"0.006000","tx_hash":...}],"total_settled":"0.010000"}
```

## Reputation bonds — collateral that slashes (PA 08 / RFB 3)

A provider posts a USDC bond; on resolution it releases (delivered) or slashes to the
claimant (underdelivered). Reputation becomes capital at risk (±100).

```bash
BID=$(curl -s localhost:8000/bond -H 'content-type: application/json' \
  -d '{"provider":"0x1...1","claimant":"0x2...2","amount":"0.01"}' | jq -r .bond_id)

curl -s localhost:8000/bond/$BID/resolve -H 'content-type: application/json' -d '{"passed": false}'
# -> {"status":"slashed","reputation_delta":-100,"tx_hash":"0x..."}   (slash settles to the claimant)
curl -s localhost:8000/bond/$BID            # read current state
```

When `KERYX_ERC8183_ENABLED=true` and a signing key is set, `POST /bond` also anchors the
bond in an on-chain ERC-8183 escrow (see `escrow` in the response). See
[ERC-8183 escrow-backed bonds](#erc-8183-escrow-backed-bonds) below.

## Streaming — pay-per-second (RFB 4)

Approve a rate; bill per second of flow. Sub-micro fractions carry across ticks (no dust).

```bash
SID=$(curl -s localhost:8000/stream -H 'content-type: application/json' \
  -d '{"payer":"0x1...1","payee":"0x2...2","rate":"0.001"}' | jq -r .stream_id)

curl -s localhost:8000/stream/$SID/tick   -H 'content-type: application/json' -d '{"seconds":"3"}'
curl -s localhost:8000/stream/$SID/pause
curl -s localhost:8000/stream/$SID/resume
curl -s localhost:8000/stream/$SID/close  -H 'content-type: application/json' -d '{}'
# tick -> {"billed":"0.003000","total_settled":"0.003000","status":"open",...}
```

## User-centric royalties — pay who you played (PA 05)

A listener's budget splits only across creators they actually engaged, by real play counts,
with play-gating (`min_count`) so a skip earns nothing.

```bash
curl -s localhost:8000/royalties -H 'content-type: application/json' -d '{
  "budget": "0.01",
  "plays": [{"wallet":"0xa...a","count":30},{"wallet":"0xb...b","count":10},{"wallet":"0xc...c","count":0}],
  "min_count": 1
}'
# -> {"recipients":[{"wallet":...,"plays":30,"amount":"0.007500"}],"gated_out":1,"total_settled":"0.010000"}
```

## Quadratic funding — breadth beats size (PA 03/07)

A match pool weighted by `(Σ√contribution)²`, so many small backers beat one big donor.

```bash
curl -s localhost:8000/qf -H 'content-type: application/json' -d '{
  "pool": "0.01",
  "projects": [
    {"wallet":"0xa...a","contributions":["1","1","1","1"]},
    {"wallet":"0xb...b","contributions":["4"]}
  ]
}'
# -> A (4 backers) matched 0.008, B (1 backer) matched 0.002 — equal direct totals, breadth wins.
```

## Retroactive funding — reward what proved valuable (PA 07)

`POST /retro` — pay out a pool *after the fact* by realized impact (distinct engagers),
weighted quadratically (impact²) so breadth of impact wins.

```bash
curl -s localhost:8000/retro -H 'content-type: application/json' -d '{
  "pool": "0.01",
  "projects": [{"wallet":"0xa...a","impact":40},{"wallet":"0xb...b","impact":10}]
}'
# -> impact 40 vs 10 -> 0.0094 vs 0.0006 awarded; broad impact wins big.
```

## Audit — verify an attestation independently

`POST /attestation/verify` — recompute an attestation's signature against its `agent_pubkey`.
Paste the `attestation` (+ `citations`) from an `/ask` response; tampering flips `verified`.

```bash
curl -s localhost:8000/attestation/verify -H 'content-type: application/json' -d @attestation.json
# -> {"verified": true, "agent_pubkey": "0x…", "query_hash": "0x…", "citations": 4}
```

A paste-and-verify UI is the web **`/audit`** page.

## Send with a memo — provenance travels with the payment

`POST /send` — a plain USDC transfer whose memo carries *why* it was paid (a citation URL, an
attestation hash, a job id); `GET /memo/{tx_hash}` reads it back. Inspired by
`circlefin/recibo` + the Arc "Send USDC with a memo" quickstart (on-chain this is the transfer
memo field).

```bash
TX=$(curl -s localhost:8000/send -H 'content-type: application/json' \
  -d '{"to":"0xa...a","amount":"0.01","kind":"citation","ref":"https://example.com/post","memo":"g=0.91"}' | jq -r .tx_hash)
curl -s localhost:8000/memo/$TX     # -> {"found": true, "memo": "...", "meta": {"kind":"citation","scheme":"plaintext",...}}
curl -s 'localhost:8000/memos?kind=citation&limit=10'   # recibo-style receipt feed, filterable by kind
```

The memo is a structured **recibo envelope** (`kind`, `ref`, `note`, routing, `version`,
`scheme`) ported from `circlefin/recibo`; `kind` is a small taxonomy
(`citation|invoice|swap|refund|job|…`).

## Stablecoin swap — USDC ↔ EURC (arc-stablecoin-fx)

`POST /swap/quote` estimates, `POST /swap` executes: gross at the mock Arc FX rate less an app
fee in bps (`KERYX_SWAP_APP_FEE_BPS`, default 30). Ported from `circlefin/arc-stablecoin-fx`
(`estimateSwap`/`executeSwap` + `customFee`); the real on-chain path is `rail/appkit` `swapOnArc`.

```bash
curl -s localhost:8000/swap/quote -H 'content-type: application/json' \
  -d '{"token_in":"USDC","token_out":"EURC","amount_in":"10"}'
# -> {"amount_out":"9.172400","app_fee":"0.027600","app_fee_bps":30,"effective_rate":"0.917240"}
curl -s localhost:8000/swap -H 'content-type: application/json' \
  -d '{"token_in":"USDC","token_out":"EURC","amount_in":"10","to":"0xb...b"}'   # settles net to `to`
```

## Split-bill money request — request money, split across payers (arc-p2p-payments)

`POST /request` opens a request: a payee asks payers to cover a total, split dust-free; each
payer fulfils their share, which settles to the payee. Ported from `circlefin/arc-p2p-payments`.

```bash
RID=$(curl -s localhost:8000/request -H 'content-type: application/json' \
  -d '{"payee":"0xe...e","payers":["0xa...a","0xb...b","0xd...d"],"total":"0.10"}' | jq -r .id)
curl -s localhost:8000/request/$RID/fulfil -H 'content-type: application/json' -d '{"payer":"0xa...a"}'
curl -s localhost:8000/request/$RID    # -> {"status":"open","collected":"0.033334","outstanding":"0.066666",...}
```

## Prepaid credits — top up once, draw down per action (arc-commerce)

`POST /credits/topup` settles USDC to a treasury and credits a balance; `POST /credits/spend`
draws it down per action (no further on-chain move) — batching micro-tolls into one settlement.
Ported from `circlefin/arc-commerce`.

```bash
curl -s localhost:8000/credits/topup -H 'content-type: application/json' -d '{"wallet":"0xa...a","amount":"0.05"}'
curl -s localhost:8000/credits/spend -H 'content-type: application/json' -d '{"wallet":"0xa...a","amount":"0.001","reason":"citation"}'
curl -s localhost:8000/credits/0xa...a   # -> {"balance":"0.049000","entries":[{"kind":"topup",...},{"kind":"spend",...}]}
# spending past the balance -> {"error":"insufficient_credits: have …, need …"}
```

## Approved settlements — intent → approve → execute (circle-ooak)

A batch of settlement intents is approved once (→ `wfid`), then each executes only if it
matches the approved next action, in order — nothing settles that wasn't approved. Ported from
`circlefin/circle-ooak` (`secure_tool` + `WorkflowManager`).

```bash
WF=$(curl -s localhost:8000/workflow/approve -H 'content-type: application/json' \
  -d '{"intents":[{"to":"0xa...a","amount":"0.01"},{"to":"0xb...b","amount":"0.02"}]}' | jq -r .wfid)
curl -s localhost:8000/workflow/$WF/execute -H 'content-type: application/json' -d '{"to":"0xa...a","amount":"0.01"}'
curl -s localhost:8000/workflow/$WF    # -> {"status":"approved","cursor":1,"remaining":1,"actions":[...]}
# an out-of-order or unapproved execute -> {"error":"call does not match the approved next action ..."}
```

## Refund / dispute — refund to the address bound at send (refund-protocol)

`POST /refund/{tx}` refunds a `/send` to the `refund_to` bound at pay time, carrying a dispute
reason and an initiating party. Ported from `circlefin/refund-protocol`.

```bash
TX=$(curl -s localhost:8000/send -H 'content-type: application/json' \
  -d '{"to":"0xa...a","amount":"0.01","refund_to":"0x9...9"}' | jq -r .tx_hash)
curl -s localhost:8000/refund/$TX -H 'content-type: application/json' -d '{"reason":"not_delivered","by":"arbiter"}'
# -> {"refunded":true,"refund_to":"0x9...9","reason":"not_delivered","by":"arbiter",...}
```

## Unified balance — one view of the agent's economic state (arc-multichain-wallet)

`GET /balance` rolls up settled volume, prepaid credits outstanding, and open split-bill
requests into a single summary (the unified-balance idea from `circlefin/arc-multichain-wallet`).

```bash
curl -s localhost:8000/balance
# -> {"settled":{...}, "credits":{"accounts":1,"outstanding_usdc":"0.050000"},
#     "requests":{"total":1,"open":1,"outstanding_usdc":"0.100000"},
#     "treasury":{"balance":"0.050000","sweepable":false,...}}
```

## Treasury — accumulate inflows, sweep out (arc-fintech)

Prepaid-credit top-ups settle to the treasury; `GET /treasury` reports its balance, flow
history, and a `sweepable` flag (balance ≥ `KERYX_TREASURY_SWEEP_THRESHOLD`, default 1.0).
`POST /treasury/sweep` settles the whole balance to a destination and zeroes the treasury —
the offline analogue of `circlefin/arc-fintech`'s multi-chain rebalance.

```bash
curl -s localhost:8000/treasury     # -> {"balance":"1.200000","sweepable":true,"flows":[...]}
curl -s localhost:8000/treasury/sweep -H 'content-type: application/json' -d '{"to":"0xf...f"}'
# -> {"swept":true,"amount":"1.200000","to":"0xf...f","balance":"0.000000",...}
```

## Confidential memos — redact the note in the public feed (recibo)

Pass `confidential: true` on `/send` to mark a memo confidential (recibo's `encrypt` scheme).
Its note is redacted (`🔒 confidential`) in the public `GET /memos` feed and the one-line
memo, but returned in full on a direct `GET /memo/{tx}` read — the offline analogue of a
recibo PGP memo only the counterparties can decrypt.

```bash
TX=$(curl -s localhost:8000/send -H 'content-type: application/json' \
  -d '{"to":"0xa...a","amount":"0.01","kind":"invoice","memo":"secret terms","confidential":true}' | jq -r .tx_hash)
curl -s localhost:8000/memo/$TX             # -> {"meta":{"note":"secret terms","scheme":"confidential",...}}
curl -s localhost:8000/memos | jq '.memos[0].meta.note'   # -> "🔒 confidential"
```

## Dashboard bootstrap — one call for the whole picture

`GET /status` also returns a `books` block: live counts across every primitive ledger
(prepaid credits, split-bill requests, treasury, approved workflows, memos, sends).

```bash
curl -s localhost:8000/status | jq .books
# -> {"credits":{"accounts":1,...},"requests":{"open":1,...},"treasury":{"balance_usdc":"…"},
#     "workflows":{"total":1,"active":1},"memos":2,"sends":1}
```

## Traction — settled volume across every primitive

`GET /traction` rolls up volume + payment count by primitive (the 30%-weighted judging axis).

```bash
curl -s localhost:8000/traction
# -> {"total_volume_usdc":"0.057000","total_payments":25,"by_kind":{"payout":{"count":9,...},...}}
```

Generate volume with the fleet (agents are the users):

```bash
python -m agent.capabilities_fleet --rounds 20    # drives every primitive against the agent
```

`POST /demo/run {rounds}` generates sample volume server-side (runs every primitive N rounds)
— the dashboard's "Generate sample volume" button. `GET /status` is a one-call dashboard
bootstrap (live rail/embedder/LLM, capability flags, traction + citation metrics).
`GET /reconcile` checks the off-chain ledger against chain (matched vs unverified, reconciled
total) when `KERYX_LEDGER_VERIFY_CHAIN` is on.

```bash
curl -s localhost:8000/status     | jq '{rail, traction: .traction.total_volume_usdc}'
curl -s localhost:8000/reconcile  # {"enabled":true,"verified":N,"unverified":M,"in_sync":bool}
```

---

## On-chain reads (opt-in)

| Endpoint | Enable with | Returns |
| --- | --- | --- |
| `GET /identity` | `KERYX_ERC8004_ENABLED=true` | the agent's ERC-8004 onchain identity |
| `POST /reputation` `{agent_id, g}` | `+ KERYX_AGENT_PRIVATE_KEY` | records grounding→reputation (score = round(100·g)) |
| `GET /validation/{request_hash}` | `KERYX_ERC8004_ENABLED=true` | ERC-8004 ValidationRegistry status |
| `GET /job/{id}` | `KERYX_ERC8183_ENABLED=true` | ERC-8183 AgenticCommerce job state |
| `GET /circle/transaction/{id}` | `KERYX_CIRCLE_API_KEY` | Circle W3S transaction status |

All return `{"enabled": false}` until configured, and degrade to an `error` field (never a
500) on a flaky RPC. Contract addresses default to the verified Arc Testnet registries
(`docs.arc.io`); see `.env.example`.

## ERC-8183 escrow-backed bonds

By default a reputation bond is an in-memory state machine whose slash settles via the rail.
When `KERYX_ERC8183_ENABLED=true` **and** `KERYX_AGENT_PRIVATE_KEY` is set, `POST /bond`
additionally anchors the bond in a real on-chain ERC-8183 job escrow — proof the funds exist
— and the response carries `escrow: {job_id?, tx_hash}`. This path needs a funded wallet
(testnet USDC) and is best-effort: any RPC/funding failure degrades to the offline bond
without breaking the request. Note: the reference ERC-8183 contract releases escrow to the
provider on `complete`, so the slash-to-claimant transfer always goes through the rail.
