# Keryx — Build Plan

Companion to `prd.md`. Window: today (Jun 19) → Jun 29 morning ≈ **10 build days**. Team: small, going hard, two Claude Code instances (CC-A, CC-B). Submit early and often.

---

## Stack (locked)

- **Agent + grounding verifier:** Python / FastAPI. Keeps us on the `arc-nanopayments` LangChain reference instead of porting it.
- **Frontend + dashboard:** Next.js on Vercel. Ask-anything page + live ledger.
- **Off-chain store:** **Neon** (serverless Postgres). Registry + source cache + agent session state only. **No Supabase** — DB, auth, or otherwise.
- **Auth:** signed wallet auth for agents. No session provider.
- **Settlement ledger:** **Arc** (chain is canonical). Postgres holds only a fast read-index.
- **Rail:** Circle x402 + Gateway Nanopayments + Wallets + USDC on Arc testnet.
- **Source ingest:** RSSHub (`DataItem.link` + `author`).

## Fork these first

- `circlefin/arc-nanopayments` — LangChain paying agent + x402 seller endpoints + Gateway batching. **Start here.**
- `the-canteen-dev/circle-agent` — Canteen explainer companion.
- Pull live docs via `arc-canteen context sync` so both Claude Codes build against current Arc/Circle context.

## Proposed repo layout

```
keryx/
  rail/            # CC-A: x402 seller, EIP-3009 verify, Gateway batch, wallet provisioning
  agent/           # CC-B: research agent, retrieval, grounding verifier, attestation signer
  registry/        # author -> wallet mapping + RSSHub ingest (shared, CC-B leads)
  web/             # Next.js page + live dashboard (chain reads)
  shared/          # types, attestation schema, env
  README.md        # built for a reviewer with no context
```

## Data model (Neon — index/registry/cache only)

- `authors(id, source_domain|author_url, wallet_address, meta, created_at)`
- `sources(id, url, title, author_ref, content_hash, raw_dataitem, fetched_at)`
- `sessions(id, agent_wallet, budget_total, budget_spent, per_source_cap, created_at)`
- `citations_index(id, session_id, source_id, grounding_score, amount, tx_hash, settled_at)` — *mirror of chain for dashboard speed; chain is canonical*

## Core endpoints

- `POST /ask {query, budget?}` → runs the agent; returns `{answer, citations[], attestation, total_settled}`
- `POST /agent/session` → create + fund an agent wallet/session
- `POST /cite {source_id, grounding_proof, payment}` → **x402-protected**: 402 with requirements → retry with EIP-3009 auth → verify + record + batch via Gateway → receipt
- `GET /ledger` → chain reads (+ index) for the dashboard

---

## Workstream split

### CC-A — The Rail (critical path)
Owns everything between a signed authorization and a cleared on-chain settlement.
- Fork `arc-nanopayments`; stand up wallet provisioning (Circle Wallets) for agents + authors.
- Implement the x402 seller flow on `/cite` (402 → EIP-3009 verify → accept).
- Wire Gateway batched settlement; read tx back for the ledger.
- Expose a clean `settle(source, amount, payment_auth) -> receipt` interface for CC-B.

### CC-B — The Agent + Verifier (the moat + the score)
Owns retrieval, reasoning, grounding, and the signed attestation. Builds against a **mock rail** until M2 so it's never blocked.
- RSSHub ingest → `sources` + author→wallet `registry`.
- Research agent: retrieve → answer → budget/cap management.
- Grounding verifier: similarity + LLM judge → `g`; gate at `T`; weighted amount.
- Attestation signer: `{query_hash, answer_hash, citations[], agent_pubkey, ts}`.

**Integration point:** ~Day 4, CC-B swaps the mock rail for CC-A's `settle()`.

---

## Milestones

| Phase | Days | Done when… | Owner |
| --- | --- | --- | --- |
| **M0 — Rail spike** | 1 | **One test-USDC nanopayment clears on Arc, end to end.** Nothing is built on top until this passes. | CC-A |
| **M1 — Two sides stubbed** | 1–3 | `/cite` does the full x402→Gateway dance; agent answers + grounds against the mock rail; registry seeded from RSSHub. | CC-A + CC-B |
| **M2 — Integration** | 4 | Agent settles real test-USDC per genuinely-cited source through CC-A's `settle()`. Attestation emitted + verifiable. | both |
| **M3 — Surface** | 5–7 | Next.js ask page + live ledger (chain reads) deployed on Vercel. Open `/ask` endpoint live. **Submit v1 on Day 7.** | web + both |
| **M4 — Traction run** | 8–9 | Agent fleet running real queries; endpoint opened to Discord; team-vs-external volume tracked. Numbers accumulating. | all |
| **M5 — Ship** | 10 | <3 min video, README polished for a cold reviewer, live link verified, final resubmission. | all |

## Critical path

`M0 single payment clears` → everything. If M0 slips, the whole plan slips. CC-A does nothing else until it's green. CC-B works the mock rail in parallel so a slow M0 doesn't idle the team.

## Definition of done (per layer)

- **Rail:** a fresh agent wallet can settle N citations in a batch and the tx is readable on the Arc explorer.
- **Agent:** given a query, returns an answer + ≥1 cited source + ≥1 evaluated-but-not-cited source, with a signed attestation.
- **Web:** a stranger can ask a question and watch a real USDC payment land on an author wallet, then see it in the ledger.

## Open items (blocking — need from the team now)

1. **ARC-cli + testnet provisioned?** Is `arc-canteen login` done, RPC set (`$RPC`), and a faucet-funded wallet ready — or is that my first task under M0? (Observed `eth_chainId` from the CLI doc is `0x4cef52`; verify on setup.)
2. **Owners:** who drives CC-A and who drives CC-B? Rail experience should sit on CC-A.

## Submission checklist

- [ ] Public GitHub repo, reviewer-ready README
- [ ] Live deployed link (Vercel) verified from a clean browser
- [ ] Video demo < 3 min (ask → research → inline citations → live payments → ledger)
- [ ] Traction answers: agents/users onboarded, problem solved
- [ ] v1 submitted ~Day 7; final resubmission Day 10
- [ ] Dashboard clearly distinguishes team vs external settlement volume
