# CLAUDE.md

Operating manual for the two Claude Code instances building **Keryx**. Read `AGENTS.md` for the project + ground rules and `docs.md` for what to clone. This file is *how we work*.

## On session start

1. Read `AGENTS.md`, `prd.md`, `plan.md`, `docs.md`.
2. Confirm which instance you are: **CC-A (rail)** or **CC-B (agent + verifier)**.
3. Run `arc-canteen context sync` and load the Arc/Circle context.
4. Check the M0 gate status before building anything on the rail.

## The two-instance protocol

We work in parallel against a fixed contract so neither instance blocks the other.

**CC-A — `rail/`**
Owns everything from a signed authorization to a cleared on-chain settlement. Forks `circlefin/arc-nanopayments` and customizes its seller endpoint into our `/cite` flow. Exposes a stable interface for CC-B:

```
settle(intents: list[CitationIntent]) -> list[Receipt]
# CitationIntent = { source_id, author_wallet, amount, payment_auth }
# Receipt        = { source_id, tx_hash, status }
```
…and the HTTP `/cite` contract: `402` with payment requirements → retry with EIP-3009 auth → verify → record → Gateway batch → receipt.

**CC-B — `agent/` + `registry/`**
Owns retrieval, reasoning, grounding, attestation. Builds against `shared/MockRail.settle()` (returns fake receipts) until **M2**, then swaps in CC-A's real `settle()`. Never blocked by the rail.

**Shared contract first.** On day 1, both instances co-author `shared/` types — `CitationIntent`, `Receipt`, `Attestation` — and freeze them. Changes to `shared/` are coordinated, not unilateral, so the two sides never drift.

**Integration:** ~day 4 (M2). CC-B replaces the mock rail with the real one; first real test-USDC citation settles.

## Assemble, don't author

Before writing a module, check `docs.md` for the repo that already does it. Customize, don't recreate. Our original code is confined to:
- `agent/grounding/` — similarity + LLM-judge scoring, the `g ≥ T` gate, weighted amounts. **This is the moat.**
- `agent/attestation/` — the signed `{query_hash, answer_hash, citations[], agent_pubkey, ts}`.
- `rail/cite/` — the citation-toll endpoint built on the forked seller.
Everything else (paying-agent client, Gateway batching, retrieval, feed parsing, wallet provisioning, chain reads, UI) is glue over existing OSS.

## Conventions

- `rail/` + `agent/`: Python / FastAPI (stay on the LangChain reference). `web/`: Next.js + Tailwind. Chain reads via viem.
- Store: Neon Postgres; pgvector for grounding similarity. **Never Supabase.**
- Secrets in `.env` (gitignored). `$RPC` from `arc-canteen` (`arc-canteen shell-init >> ~/.zshrc`). Rotate with `arc-canteen rotate-rpc-key`.
- Settlement amounts are config, not hardcoded: floor `$0.000001`, per-citation toll `$0.001–$0.01`, grounding threshold `T=0.5`.
- Commit small, push often. Submit a working v1 ~day 7; the form accepts resubmissions.

## Do / Don't

- ✅ Clone MIT/permissive repos, keep their LICENSE, attribute, customize.
- ✅ Make the rail green (M0) before anything else.
- ✅ Show an *evaluated-but-not-cited* source in every answer — proves we pay on citation, not fetch.
- ✅ Read settlement state from chain for the dashboard.
- ❌ Supabase, mainnet, real funds.
- ❌ Reimplementing x402 / Gateway / LangChain / RSSHub by hand.
- ❌ Letting the off-chain index become the source of truth for payments.

## Command cheat-sheet

```
# Arc dev tooling (Canteen)
arc-canteen status
arc-canteen context sync
arc-canteen rpc eth_blockNumber
arc-canteen update-product / update-traction
arc-canteen submit-puzzle

# Circle CLI — wallets, x402 payments, faucet
npm install -g @circle-fin/cli       # Node v20.18.2+

# Dev
uvicorn rail.main:app --reload       # CC-A
uvicorn agent.main:app --reload      # CC-B
cd web && pnpm dev                    # surface
```

## Definition of done

- **Rail:** a fresh agent wallet settles N citations in a batch; tx readable on the Arc explorer.
- **Agent:** a query returns an answer + ≥1 cited + ≥1 evaluated-not-cited source + a verifiable attestation.
- **Web:** a stranger asks a question and watches real USDC land on an author wallet, then in the ledger.
