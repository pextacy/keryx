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
