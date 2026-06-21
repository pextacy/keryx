# Keryx capabilities — endpoint reference

Every nanopayment primitive the agent exposes, with copy-paste `curl`. The agent runs at
`http://127.0.0.1:8000` (`make agent` or `uvicorn agent.main:app`). All amounts are test-USDC
strings (6-dp); every settling endpoint clears through the active rail (MockRail by default,
the real x402+Gateway `HttpRail` when `KERYX_RAIL=http`). A live UI for all of these is at
`/capabilities` in the web app (`cd web && pnpm dev`).

Splits are **exact**: every payout/match sums to the input down to the micro-USDC, with no
dust and never overpaying. On-chain read endpoints are **opt-in** and return `{"enabled": false}`
until their `KERYX_*_ENABLED` flag is set.

## Vendored Circle ports

Beyond the original nanopayment primitives, several capabilities build over Circle's
open-source Arc repos — adopted in-tree as standalone apps under `apps/` (Foundry projects
under `contracts/vendor/`), see [`NOTICE`](../NOTICE). Each agent endpoint is the offline
analogue of the upstream's pattern, settling through the same rail (the approved-action
workflow runs `apps/circle-ooak` directly):

| Capability | Endpoints | Ported from |
| --- | --- | --- |
| Stablecoin swap (USDC↔EURC) | `POST /swap/quote`, `/swap` | `arc-stablecoin-fx` |
| Split-bill money request | `POST /request`, `/request/{id}/fulfil` | `arc-p2p-payments` |
| Prepaid credits + tiers | `POST /credits/topup`, `/spend`, `GET /credits/tiers` | `arc-commerce` |
| Multi-item order checkout | `POST /order`, `/order/{id}/checkout` | `arc-commerce` |
| Approved-action workflow | `POST /workflow/approve`, `/{id}/execute` | `circle-ooak` |
| Refund / dispute | `POST /refund/{tx}` | `refund-protocol` |
| Structured + confidential + threaded memos | `GET /memos`, `/memo/{tx}/thread` | `recibo` |
| Treasury + sweep | `GET /treasury`, `POST /treasury/sweep` | `arc-fintech` |
| Recurring payment schedule | `POST /schedule`, `/schedule/{id}/run` | `arc-fintech` |
| Gateway unified balance | `POST /gateway/deposit`, `/spend`, `/transfer`, `GET /gateway/{wallet}` | `arc-multichain-wallet` |
| Milestone escrow | `POST /escrow`, `/escrow/{id}/release` | `arc-escrow` |
| ERC-8183 job escrow | `GET /job/{id}` (+ bond anchor) | `arc-escrow` |
| Agent-tool manifest | `GET /agent/tools`, `/capabilities` | `agent-stack-starter-kits` |
| Unified balance summary | `GET /balance`, `/status` `books` | (aggregates the above) |

The full machine-readable index (with a copy-paste example per capability) is `GET /capabilities`;
`make kitchen-sink` curls every primitive end-to-end and prints PASS/FAIL per capability (29 checks).

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

## Credit tiers — buy packages at a bulk discount (arc-commerce)

`GET /credits/tiers` lists purchasable packages; paying more USDC grants bonus credits per
dollar. `POST /credits/topup` with a `tier` settles the tier's USDC and credits the
bonus-inflated amount (plain `amount` still credits 1:1).

```bash
curl -s localhost:8000/credits/tiers
# -> {"tiers":[{"name":"pro","usdc":"0.10","bonus_bps":1000,"credits":"0.110000"},...]}
curl -s localhost:8000/credits/topup -H 'content-type: application/json' -d '{"wallet":"0xa...a","tier":"pro"}'
# -> {"topped_up":true,"paid_usdc":"0.10","credited":"0.110000","balance":"0.110000",...}
```

## Multi-item order — bundle line-items, settle at checkout (arc-commerce)

Bundle line-items paying different recipients (e.g. a research bundle: source author +
validator + indexer) into one order, then settle them together at checkout — the
multi-recipient generalisation of arc-commerce's USDC checkout.

```bash
OID=$(curl -s localhost:8000/order -H 'content-type: application/json' -d '{
  "items":[{"description":"source author","to":"0xa...a","amount":"0.003"},
           {"description":"validator","to":"0xb...b","amount":"0.002"}]
}' | jq -r .id)
curl -s localhost:8000/order/$OID/checkout   # settles every line; status "paid" or "partial"
curl -s localhost:8000/order/$OID            # -> {"total":"0.005000","paid":"0.005000","items":[...]}
```

## Gateway unified balance — deposit cross-chain, spend on Arc, transfer back out (arc-multichain-wallet)

Deposit USDC from several source chains (`arcTestnet`, `avalancheFuji`, `baseSepolia`) into one
unified balance, then spend it on Arc — the offline analogue of Circle Gateway's unified balance.
`transfer` ports the wallet's other headline move: a cross-chain **burn/mint** that takes funds
back out of the unified balance onto a destination chain (optionally to an external recipient).

```bash
curl -s localhost:8000/gateway/chains   # -> {"chains":["arcTestnet","avalancheFuji","baseSepolia"]}
curl -s localhost:8000/gateway/deposit -H 'content-type: application/json' \
  -d '{"wallet":"0xa...a","chain":"avalancheFuji","amount":"0.5"}'
curl -s localhost:8000/gateway/spend -H 'content-type: application/json' \
  -d '{"wallet":"0xa...a","to":"0xc...c","amount":"0.2"}'   # draws the unified pool, settles on Arc
curl -s localhost:8000/gateway/transfer -H 'content-type: application/json' \
  -d '{"wallet":"0xa...a","destination_chain":"baseSepolia","amount":"0.1","recipient":"0xd...d"}'
curl -s localhost:8000/gateway/0xa...a   # -> {"balance":"0.200000","by_chain":{...},"withdrawals":[...]}
```

## Milestone escrow — lock a total, release in approved tranches (arc-escrow)

A client escrows a total split across named milestones; each releases its tranche to the
provider on approval, settling via the rail — the staged-delivery generalisation of
arc-escrow's agreement→validate→release flow.

```bash
EID=$(curl -s localhost:8000/escrow -H 'content-type: application/json' -d '{
  "client":"0xa...a","provider":"0xb...b",
  "milestones":[{"label":"draft","amount":"0.01"},{"label":"final","amount":"0.02"}]
}' | jq -r .id)
curl -s localhost:8000/escrow/$EID/release -H 'content-type: application/json' -d '{"index":0}'
curl -s localhost:8000/escrow/$EID   # -> {"status":"open","released":"0.010000","locked":"0.020000",...}
```

## Recurring schedule — fixed amount per run for N runs (arc-fintech)

A payer commits to pay a payee a fixed amount for a number of runs; each run settles one
installment via the rail — the discrete subscription/payroll counterpart to streaming.

```bash
SID=$(curl -s localhost:8000/schedule -H 'content-type: application/json' \
  -d '{"payer":"0xa...a","payee":"0xb...b","amount":"0.002","runs":3}' | jq -r .id)
curl -s localhost:8000/schedule/$SID/run     # settle one installment; repeat per run
curl -s localhost:8000/schedule/$SID/cancel  # stop further runs (paid runs stand)
curl -s localhost:8000/schedule/$SID   # -> {"runs_done":1,"runs_left":2,"paid":"0.002000",...}
```

## Confidential + threaded memos — recibo encrypt scheme + reply threads (recibo)

Pass `confidential: true` on `/send` to mark a memo confidential (recibo's `encrypt` scheme):
its note is redacted (`🔒 confidential`) in the public `GET /memos` feed but returned in full
on a direct `GET /memo/{tx}` read. Pass `reply_to: <tx>` to thread a memo to a prior one;
`GET /memo/{tx}/thread` walks ancestors + replies (a refund auto-threads to its original send).

```bash
TX=$(curl -s localhost:8000/send -H 'content-type: application/json' \
  -d '{"to":"0xa...a","amount":"0.01","kind":"invoice","memo":"secret terms","confidential":true}' | jq -r .tx_hash)
curl -s localhost:8000/memo/$TX             # -> {"meta":{"note":"secret terms","scheme":"confidential",...}}
curl -s localhost:8000/memos | jq '.memos[0].meta.note'   # -> "🔒 confidential"
# threaded:
RE=$(curl -s localhost:8000/send -d '{"to":"0xa...a","amount":"0.01","memo":"paying it","reply_to":"'$TX'"}' \
  -H 'content-type: application/json' | jq -r .tx_hash)
curl -s localhost:8000/memo/$RE/thread | jq '.ancestors[0].meta.note'   # -> "secret terms"
```

## Discovery — capabilities index + agent tools

`GET /capabilities` is a machine-readable index of every primitive (name, category, endpoints,
and the Circle upstream it's ported from). `GET /agent/tools` returns the primitives as
tool-use schemas (Claude Agent SDK / OpenAI function-calling), so another agent can discover
and invoke Keryx with JSON — the `circlefin/agent-stack-starter-kits` idea.

```bash
curl -s localhost:8000/capabilities | jq '{count, ported, by_category}'
# -> {"count":21,"ported":14,"by_category":{"split":4,"settlement":9,...}}
curl -s localhost:8000/agent/tools | jq '.tools[].name'   # ask, send_payment, swap_stablecoin, ...
```

## History — unified settlement activity feed

`GET /history` is the raw stream of every settlement that cleared the rail (most recent first),
optionally filtered by `kind` — distinct from `/memos` (provenance notes).

```bash
curl -s 'localhost:8000/history?limit=25'          # all kinds
curl -s 'localhost:8000/history?kind=swap&limit=10' # only swaps
# -> {"count":N,"settlements":[{"seq":..,"kind":"swap","amount":"..","wallet":"0x..","tx_hash":"0x.."}]}
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
