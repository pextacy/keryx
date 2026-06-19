# AGENTS.md

Portable agent context for **Keryx**. Any coding agent (Claude Code, aider, cursor, codex) reads this first. Claude-Code-specific operating rules live in `CLAUDE.md`; the external source map lives in `docs.md`.

## What we're building

Keryx — a citation-toll layer for the agent web. A paying research agent answers a query, proves which sources actually grounded its answer, and settles a sub-cent USDC nanopayment to each cited author on Arc. *Your work earns every time an agent cites it.* Full product spec: `prd.md`.

## Ground rules (non-negotiable)

1. **M0 gate.** Do not build anything on top of the rail until **one test-USDC nanopayment clears end-to-end on Arc.** If that isn't green, that's the only task.
2. **Assemble, don't author.** Clone and customize the open-source skeletons in `docs.md`. Do not reimplement payments, agents, retrieval, or feed-parsing from scratch — they already exist under permissive licenses. Our *original* code lives in two places only: the grounding/attestation layer, and the `/cite` citation-toll flow.
3. **No Supabase.** Anywhere — DB, auth, storage. Use Neon (Postgres + pgvector). Agent auth is signed-wallet, not a session provider.
4. **Chain is the ledger.** Settlement clears on Arc; that's canonical. Postgres holds only a fast read-index, the author→wallet registry, and source cache.
5. **Testnet only.** Arc testnet + test USDC. No mainnet, no real funds.
6. **Keep upstream LICENSE files.** When we vendor a repo, keep its LICENSE and attribute. Our additions are MIT.

## Read order

`AGENTS.md` (this) → `prd.md` (what + why) → `plan.md` (milestones + workstream split) → `docs.md` (what to clone) → `CLAUDE.md` (how we operate).

## Repo map

```
rail/      payments: x402 seller, EIP-3009 verify, Gateway batch, wallets   (CC-A)
agent/     research agent, retrieval, grounding verifier, attestation       (CC-B)
registry/  author->wallet map + RSSHub ingest                               (CC-B)
web/       Next.js ask page + live ledger (chain reads)
shared/    types: CitationIntent, Receipt, Attestation
```

## Get Arc/Circle context into your session

```
arc-canteen context sync         # clone/pull docs + sample codebases
arc-canteen context | <agent>    # pipe AGENTS.md + path manifest to your coding agent
```
