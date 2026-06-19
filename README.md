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

## Quickstart (Python: rail + agent)

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # fill in RPC, Neon URL, keys

pytest                          # frozen-contract tests
uvicorn rail.main:app --reload  # CC-A  -> http://127.0.0.1:8000/healthz
uvicorn agent.main:app --reload # CC-B  -> http://127.0.0.1:8000/healthz
```

## Quickstart (web)

```bash
cd web && pnpm install && pnpm dev   # http://localhost:3000
```

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

**Phase 0 (Foundation) complete** — scaffold, frozen `shared/` contract, Neon schema,
CI, env. See [`docs/phases.md`](docs/phases.md) for the full phase plan and
[`DECISIONS.md`](DECISIONS.md) for open decisions (notably the rail language question).

## Licensing

Our code is MIT (see [`LICENSE`](LICENSE)). Vendored upstreams keep their own licenses
and are attributed in [`NOTICE`](NOTICE).
