# Keryx

> Your work earns every time an agent cites it.

Keryx is a **citation-toll layer for the agent web**. A paying research agent answers a
query, proves which sources actually grounded its answer, and settles a sub-cent USDC
nanopayment to each cited author on **Arc**. Payment is on *citation*, not on *fetch* —
a source that was read but didn't ground the answer earns $0, visibly.

Built for the Lepton Agents Hackathon (Canteen × Circle, on Arc). Full spec in
[`docs/prd.md`](docs/prd.md); roadmap in [`docs/phases.md`](docs/phases.md).

## Architecture

```
rail/      payments: x402 seller, EIP-3009 verify, Gateway batch, wallets   (CC-A)
agent/     research agent, retrieval, grounding verifier, attestation       (CC-B)
registry/  author->wallet map + RSSHub ingest                               (CC-B)
web/       Next.js ask page + live ledger (chain reads via viem)
shared/    frozen contract: CitationIntent, Receipt, Attestation, Rail
db/        Neon migrations (index/registry/cache only — chain is canonical)
```

**Chain is the ledger.** Settlement clears on Arc; Postgres (Neon + pgvector) holds only
a fast read-index, the author→wallet registry, and a source cache. Never Supabase.

## Quickstart (Python: agent + grounding moat)

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                  # optional; sane defaults built in

pytest                                # 31 tests (contract, grounding, attestation, pipeline, ledger)
uvicorn agent.main:app --reload       # CC-B -> http://127.0.0.1:8000

# Ask a question (full citation loop against the mock rail):
curl -s -X POST localhost:8000/ask -H 'content-type: application/json' \
  -d '{"query":"How do Gateway nanopayments settle sub-cent USDC on Arc?"}' | jq
# Traction metrics + ledger:
curl -s localhost:8000/metrics | jq
# Generate volume:
python -m agent.fleet --n 20
```

Agent endpoints: `POST /ask`, `GET /ledger`, `GET /metrics`, `GET /config`, `GET /healthz`.

## Quickstart (web surface)

```bash
cd web && pnpm install
cp .env.example .env.local            # AGENT_URL=http://127.0.0.1:8000
pnpm dev                              # http://localhost:3000  (ask page + /ledger)
```

## The rail (M0 gate + real settlement)

The x402 + Gateway SDK is TypeScript-only, so the rail is TS and bridges to the Python
agent over the frozen `shared/` contract (see `DECISIONS.md`). The Python agent settles
through `shared.rail.HttpRail` → `rail/m0_spike/payer.ts` → Circle Gateway on Arc; until
then it uses `shared.rail.MockRail` (the swap is one line).

```bash
cd rail/m0_spike && npm install
npm run generate-wallets              # AUTHOR (payee) + BUYER (funder)
# Fund BUYER with Arc testnet USDC: https://faucet.circle.com/  (needs your auth)
npm run seller                        # citation-toll seller (/cite)
npm run payer                         # rail bridge the agent settles through
npm run m0                            # drive ONE payment -> prints tx + explorer URL
```

See `rail/m0_spike/README.md` and `docs/VERIFIED-SIGNATURES.md` for the verified
constants and the full M0 procedure.

## Database

```bash
psql "$KERYX_DATABASE_URL" -f db/migrations/0001_init.sql
python scripts/db_check.py           # verifies reachability + pgvector + schema
```

## How it works (the citation loop)

1. A query arrives (our page, our agent fleet, or an external agent).
2. The agent retrieves candidate sources (RSSHub `DataItem.link` + `author`).
3. The agent generates an answer.
4. **Grounding verifier** (`agent/grounding/`, the moat): similarity + LLM-judge → `g ∈ [0,1]`.
5. For each source with `g ≥ T`, settle a citation toll: x402 → Gateway batch → Arc.
6. The agent emits a **signed attestation** (`agent/attestation/`) mapping answer → sources → amounts → tx hashes.
7. The dashboard reads the **chain** (canonical) and renders live.

## Status

All phases are **engineered and verified end-to-end against the mock/local rail**; the
only remaining steps are the live on-chain runs, which need Arc testnet USDC from the
Circle faucet (your authentication) — see `SETUP.md`.

| Phase | What's done | Gated on |
| --- | --- | --- |
| 0 Foundation | scaffold, frozen contract, Neon schema, CI, licensing | — ✅ |
| 1 M0 rail spike | verified signatures, runnable spike, seller emits correct 402 | funded tx (faucet) |
| 2 M1 agent | grounding moat + attestation + `/ask` + registry (24 tests) | — ✅ |
| 3 M2 integration | TS payer bridge + `HttpRail`; pipeline runs unchanged against it | live settlement (funds) |
| 4 M3 surface | ask page + `/ledger` + attestation viewer; prod build green | Vercel deploy + funds |
| 5 M4 traction | ledger, team-vs-external metrics, fleet runner | real volume (funds) + Discord |
| 6 M5 ship | reviewer-ready README, NOTICE | video + form submission |

See [`docs/phases.md`](docs/phases.md) for per-phase detail and [`DECISIONS.md`](DECISIONS.md)
for resolved decisions.

## Licensing

Our code is MIT (see [`LICENSE`](LICENSE)). Vendored upstreams keep their own licenses
and are attributed in [`NOTICE`](NOTICE).
