# Setup — remaining Phase 0 steps (credential-gated)

Phase 0 engineering is complete and committed. Two items in the Phase 0 checklist
require **your external accounts** and cannot be done from the codebase alone. They
match `plan.md`'s "Open items (blocking — need from the team now)". Do these, then
Phase 0's Definition of Done is fully green.

## 1. Arc / Canteen testnet (for Phase 1 / M0)

```bash
# Install + auth the Canteen CLI (not on this machine yet)
arc-canteen login
arc-canteen shell-init >> ~/.zshrc && source ~/.zshrc   # exports $RPC
arc-canteen context sync                                  # pulls Arc/Circle docs + samples

# Verify
arc-canteen status
arc-canteen rpc eth_blockNumber
arc-canteen rpc eth_chainId        # expect 0x4cef52 (already the default in config)
```

Then put the resolved RPC into `.env` as `KERYX_RPC_URL`, and fund a wallet via the
Circle CLI faucet (`@circle-fin/cli`, Node v20.18.2+) for the M0 spike.

## 2. Neon (Postgres + pgvector)

Create a Neon project (NOT Supabase), then:

```bash
cp .env.example .env                       # set KERYX_DATABASE_URL to the Neon string
psql "$KERYX_DATABASE_URL" -f db/migrations/0001_init.sql
.venv/bin/python scripts/db_check.py       # expects: reachable + pgvector + schema OK
```

## Already done (no action needed)

- Repo scaffold, frozen `shared/` contract, config surface, migrations, CI,
  env template, licensing/NOTICE, web stub — all committed.
- Local verification: `ruff` clean, `mypy --strict` clean, 8 tests pass, both
  `uvicorn` apps serve `/healthz` + `/config`.

## Heads-up before Phase 2

See [`DECISIONS.md`](DECISIONS.md): the forked `arc-nanopayments` is **TypeScript
(LangChain.js + Next.js), Apache-2.0**, and ships a `supabase/` dir — both conflict
with the planned Python/FastAPI + no-Supabase stack. Decide the rail language before
writing `rail/`.
