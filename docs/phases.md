# Keryx — Production Phases

Execution roadmap derived from `prd.md`, `plan.md`, `docs.md`, `AGENTS.md`, and `CLAUDE.md`. This file turns the M0–M5 milestones into granular, production-ready phases: each phase has an objective, owner, entry gate, task breakdown, deliverables, and an explicit Definition of Done (DoD) that must be green before the next phase starts.

**Window:** Jun 19 → Jun 29 (~10 build days). **Two instances:** CC-A (rail) + CC-B (agent/verifier), working in parallel against a frozen `shared/` contract.

**The one hard gate:** Phase 1 (M0) must be green — one test-USDC nanopayment clears end-to-end on Arc — before anything is built on top of the rail. CC-B is never blocked because it builds against `shared/MockRail.settle()` until Phase 3.

**Legend:** `[CC-A]` rail · `[CC-B]` agent/verifier · `[BOTH]` coordinated · `[WEB]` surface. ✅ = production-ready acceptance criterion.

---

## Phase 0 — Foundation & Shared Contract  `Day 0–1`  `[BOTH]`

Stand up the repo, environment, and the frozen type contract so the two instances can build in parallel without drift. No business logic yet.

**Entry gate:** none (start here).

### Tasks
- **Repo scaffold** — create `rail/`, `agent/`, `registry/`, `web/`, `shared/` per the repo map in `AGENTS.md`. Add root `README.md` (reviewer-first, no context assumed).
- **Clone & vendor** (per `docs.md` clone order):
  - `git clone circlefin/arc-nanopayments` (the base we build on)
  - `git clone the-canteen-dev/circle-agent` (reference patterns)
  - `arc-canteen context sync` (pulls `context-arc`: docs + 5 sample codebases)
  - RSSHub: run local instance or point at hosted.
  - ✅ Confirm each upstream `LICENSE` is permissive/MIT; copy into vendored dirs + add a root `NOTICE` with attribution. Our additions are MIT.
- **Environment & secrets**
  - `.env.example` committed; real `.env` gitignored.
  - `arc-canteen shell-init >> ~/.zshrc`; `$RPC` resolves. `arc-canteen login` done; faucet-funded wallet ready (resolves plan.md open item #1).
  - ✅ `arc-canteen status` green; `arc-canteen rpc eth_blockNumber` returns; verify `eth_chainId == 0x4cef52`.
  - Neon project created (Postgres + pgvector extension enabled). **Not Supabase.** Connection string in `.env`.
- **Freeze `shared/` contract** (co-authored, then frozen — changes are coordinated, never unilateral):
  - `CitationIntent = { source_id, author_wallet, amount, payment_auth }`
  - `Receipt = { source_id, tx_hash, status }`
  - `Attestation = { query_hash, answer_hash, citations[], agent_pubkey, ts }`
  - `MockRail.settle(intents) -> list[Receipt]` returning deterministic fake receipts (CC-B's dependency until Phase 3).
- **Config surface** (config, not hardcoded): floor `$0.000001`, per-citation toll `$0.001–$0.01`, grounding threshold `T=0.5`. Centralize in `shared/config`.
- **Data model migrations** (Neon — index/registry/cache only, chain stays canonical):
  - `authors(id, source_domain|author_url, wallet_address, meta, created_at)`
  - `sources(id, url, title, author_ref, content_hash, raw_dataitem, fetched_at)`
  - `sessions(id, agent_wallet, budget_total, budget_spent, per_source_cap, created_at)`
  - `citations_index(id, session_id, source_id, grounding_score, amount, tx_hash, settled_at)`
- **CI baseline** — lint + typecheck + test runner for `rail/`, `agent/` (Python/FastAPI), `web/` (Next.js). Pre-commit hooks.

### Deliverables
Scaffolded repo, vendored upstreams with LICENSE/NOTICE, working `.env`, frozen `shared/` types + `MockRail`, Neon schema migrated, green CI skeleton.

### DoD
✅ Both instances can run `uvicorn rail.main:app --reload` and `uvicorn agent.main:app --reload` with empty-but-importable apps · ✅ `shared/` types importable from both sides and frozen · ✅ Neon reachable with pgvector · ✅ CI passes on an empty commit.

---

## Phase 1 — M0: Rail Spike (THE GATE)  `Day 1`  `[CC-A]`

**One test-USDC nanopayment clears end-to-end on Arc.** This is the only hard gate in the project. CC-A does nothing else until it is green. CC-B is unaffected (works the mock rail).

**Entry gate:** Phase 0 DoD green (env, RPC, faucet wallet).

### Tasks
- Verify the real API signatures against live sources **at build time** (never trust signatures reproduced from planning docs): x402 headers, Gateway batch-submit shape, EIP-3009 fields — against `arc-nanopayments` source + `developers.circle.com/gateway/nanopayments`, `docs.arc.network`, `developers.circle.com/agent-stack/circle-cli`.
- Provision two wallets via Circle CLI/SDK (`@circle-fin/cli`, Node v20.18.2+): one paying agent, one author. Fund via faucet.
- Drive a single payment through the canonical path from `arc-nanopayments`: x402 `402` → EIP-3009 signed auth → Gateway batch submit → settle on Arc.
- Read the resulting tx back; confirm it on the Arc explorer.

### Deliverables
A runnable spike script + the tx hash, viewable on the Arc explorer. Short note in repo recording the **verified** x402/Gateway/EIP-3009 signatures (so the rest of the build trusts source, not memory).

### Status (2026-06-19)
- ✅ **Signatures verified & recorded** → `docs/VERIFIED-SIGNATURES.md` (Arc constants, x402 wire shape, `@circle-fin/x402-batching` API, EIP-3009 domain) — from `arc-nanopayments` source + live RPC.
- ✅ **Runnable spike built** → `rail/m0_spike/` (canonical SDK, Supabase stripped). Builds + typechecks against the real SDK (`tsc` exit 0); seller boots and emits a correct Gateway-batched `402`; Arc RPC reachable (`0x4cef52`).
- ⏳ **Funded settlement — the only step left:** requires Arc testnet USDC from `faucet.circle.com` (a human/faucet action). Run order in `rail/m0_spike/README.md`: `generate-wallets` → fund BUYER → `npm run seller` → `npm run m0` → paste the tx hash below.

### DoD
✅ **A test-USDC nanopayment from agent wallet → author wallet is confirmed on-chain and readable on the Arc explorer.** Until this is true, it is the only open task in the project. _(Tx hash: ____________ — fill on first cleared payment.)_

---

## Phase 2 — M1: Two Sides Stubbed  `Day 1–3`  `[BOTH]`

Both workstreams reach a working v1 in parallel: the rail does the full x402→Gateway dance on `/cite`; the agent answers + grounds against the mock rail; the registry is seeded from RSSHub.

**Entry gate:** Phase 1 green (rail side). CC-B may begin as soon as Phase 0 is done.

### 2A — Rail  `[CC-A]`
- Fork `arc-nanopayments`; customize its seller endpoint → our **`POST /cite`** citation-toll flow: `402` with payment requirements → retry with EIP-3009 auth → verify → record → Gateway batch → `Receipt`.
- Wallet provisioning service (Circle Wallets) for agents + authors.
- Wire Gateway **batched** settlement (settle N intents in one batch, gasless); read tx back.
- Implement the frozen interface: `settle(intents: list[CitationIntent]) -> list[Receipt]`.
- `POST /agent/session` → create + fund an agent wallet/session.
- ✅ Reject malformed/replayed EIP-3009 auths; validate amounts against floor + per-source cap.

### 2B — Agent + Verifier  `[CC-B]` (builds on `MockRail`)
- **Registry/ingest:** RSSHub `DataItem.link` (canonical URL) + `DataItem.author` → `sources` cache + `authors` (author→wallet) registry. Seed a curated source set.
- **Research agent** (extend the `arc-nanopayments` LangChain paying agent): retrieve candidates → generate answer → budget + per-source cap management.
- **Grounding verifier — `agent/grounding/` (the moat):** similarity signal (pgvector cosine over answer spans × source passages) + LLM-judge signal (`supported|partial|unsupported` per claim + rationale) → grounding score `g ∈ [0,1]`. Gate: pay only if `g ≥ T`. Amount: floor, optionally scaled by `g`.
- **Attestation signer — `agent/attestation/`:** emit signed `{query_hash, answer_hash, [{source_url, g, amount, tx_hash}], agent_pubkey, ts}`.
- **`POST /ask {query, budget?}`** → run agent → `{answer, citations[], attestation, total_settled}`, settling through `MockRail` for now.
- ✅ Every answer carries ≥1 cited **and** ≥1 *evaluated-but-not-cited* source (proves pay-on-citation, not pay-on-fetch).

### DoD
✅ `/cite` performs the complete x402→Gateway dance against real testnet · ✅ Agent returns answer + grounded citations + attestation against the mock rail · ✅ Registry seeded from RSSHub with author→wallet mappings · ✅ Both sides unit-tested.

---

## Phase 3 — M2: Integration  `Day 4`  `[BOTH]`

CC-B swaps `MockRail` for CC-A's real `settle()`. First real test-USDC citation settles per genuinely-grounded source.

**Entry gate:** Phase 1 green + Phase 2A `settle()` + Phase 2B agent both ready against the frozen contract.

### Tasks
- Replace `shared/MockRail.settle()` call site in the agent with CC-A's real `settle(intents) -> list[Receipt]`. (No type changes — that's why `shared/` was frozen.)
- End-to-end run: `/ask` → retrieve → answer → ground → for each `g ≥ T` build `CitationIntent` → real `settle()` → Gateway batch → on-chain → attestation now carries real `tx_hash`es.
- Verify the attestation against chain state: each cited `tx_hash` resolves on the Arc explorer; amounts match.
- Persist to `citations_index` as a **mirror of chain** (dashboard read-speed only; chain stays canonical).
- ✅ Budget/cap enforcement holds under real settlement (agent stops at budget; per-source cap respected).
- ✅ Failure handling: a failed/declined settlement does not corrupt the attestation or double-pay.

### DoD
✅ **A query settles real test-USDC to author wallets per genuinely-cited source, with a verifiable attestation whose tx hashes resolve on-chain** · ✅ evaluated-but-not-cited sources logged at $0 · ✅ `citations_index` reconciles with chain.

---

## Phase 4 — M3: Surface  `Day 5–7`  `[WEB + BOTH]`  → **Submit v1 on Day 7**

The public ask page + live ledger, deployed. A stranger asks a question and watches real USDC land on author wallets.

**Entry gate:** Phase 3 green (real end-to-end settlement).

### Tasks
- **Ask page** (Next.js + Tailwind, shadcn/ui optional): question input → research → answer with **inline citations** → real-time per-author USDC nanopayments → settlement ledger.
- ✅ UI shows ≥1 *evaluated-but-not-cited* source per answer (gating visible — honest, not pay-to-fetch).
- **`GET /ledger`** powered by **chain reads via viem** (+ `citations_index` for speed). "Don't trust our DB, here's the chain."
- Live ledger view: distinct author wallets paid, citations settled, paying-agent sessions, total settled.
- **Open `/ask` endpoint** live and documented for external agents (traction enabler).
- Deploy `web/` on Vercel; verify from a clean browser with no local state.
- Attestation viewer: expose the signed attestation per answer as the audit trail.
- ✅ Reviewer-ready `README.md` (a cold reviewer clicking around without us).

### DoD
✅ Deployed Vercel link works from a clean browser · ✅ A stranger can ask → see inline citations → watch USDC land on an author wallet → see it in the ledger · ✅ Ledger reads from chain · ✅ Open `/ask` documented · ✅ **v1 submitted via the form on Day 7** (resubmission allowed).

---

## Phase 5 — M4: Traction Run  `Day 8–9`  `[ALL]`

Generate genuine settlement volume — the 30%-weighted strategic bet. Agents are the users.

**Entry gate:** Phase 4 deployed + open endpoint live.

### Tasks
- Run an **agent fleet** issuing real queries across the curated source set; accumulate settlement volume.
- **Open the endpoint to Discord** genuinely; onboard ≥1 external builder's agent.
- ✅ Dashboard labels **team vs external** volume transparently (self-generated volume is legitimate — agents are the users — but external usage leads the story).
- Track success metrics (north star = total test-USDC settled): distinct author wallets paid, distinct paying-agent sessions, citations settled, **% queries from external agents**, queries/day trend.
- Tune `T`, per-citation toll, and `g`-weighting from real data.
- Targets to beat by submission (adjustable): **1,000+ citations settled · 50+ distinct author wallets paid · ≥1 external agent integration + meaningful Discord usage.**
- Daily integration sync; mock-rail fallback if Gateway/x402 testnet quirks appear.

### DoD
✅ Numbers accumulating with team-vs-external clearly separated · ✅ ≥1 external agent integrated · ✅ targets approached/met · ✅ metrics queryable for the submission.

---

## Phase 6 — M5: Ship  `Day 10`  `[ALL]`

Final polish and resubmission.

**Entry gate:** Phase 5 numbers in hand.

### Tasks
- **Video demo < 3 min** (Loom/YouTube/Vimeo): ask → research → inline citations → live payments → ledger.
- Polish `README.md` for a cold reviewer; ensure repo is reviewer-ready end to end.
- Verify the live link one more time from a clean browser.
- Final traction answers: agents/users onboarded, problem solved.
- **Final resubmission via the form.**

### DoD (submission checklist)
- [ ] Public GitHub repo, reviewer-ready README, upstream LICENSEs + NOTICE intact
- [ ] Live Vercel link verified from a clean browser
- [ ] Video demo < 3 min (ask → research → inline citations → live payments → ledger)
- [ ] Traction answers: agents/users onboarded, problem solved
- [ ] Dashboard distinguishes team vs external settlement volume
- [ ] v1 submitted ~Day 7; final resubmission Day 10

---

## Cross-cutting (every phase)

- **Chain is the ledger.** Postgres is only a fast read-index + registry + cache. Never let the off-chain index become the source of truth for payments.
- **Assemble, don't author.** Original code lives only in `agent/grounding/`, `agent/attestation/`, and `rail/cite/`. Everything else is glue over OSS (x402, Gateway, LangChain, RSSHub, viem). Don't reimplement these by hand.
- **Verify signatures at build time.** x402 headers, Gateway batch shape, EIP-3009 fields → always against live docs + `arc-nanopayments` source, never from planning files.
- **`shared/` is frozen.** Type changes are coordinated across both instances, never unilateral.
- **Testnet only.** Arc testnet + test USDC. No mainnet, no real funds. **No Supabase**, anywhere.
- **Commit small, push often.** Submit working v1 ~Day 7; the form accepts resubmissions.
- **Security:** signed-wallet agent auth (no session provider); reject replayed/malformed EIP-3009 auths; validate amounts against floor + per-source cap; secrets in gitignored `.env`, rotate RPC via `arc-canteen rotate-rpc-key`.

## Phase → Milestone map

| Phase | Milestone | Days | Owner | Gate to next |
| --- | --- | --- | --- | --- |
| 0 Foundation | — | 0–1 | BOTH | Contract frozen, env green |
| 1 Rail spike | **M0** | 1 | CC-A | **Hard gate:** 1 payment clears on Arc |
| 2 Two sides stubbed | M1 | 1–3 | BOTH | `/cite` dance + agent on mock rail |
| 3 Integration | M2 | 4 | BOTH | Real settlement + verifiable attestation |
| 4 Surface | M3 | 5–7 | WEB+BOTH | Deployed + **v1 submitted Day 7** |
| 5 Traction run | M4 | 8–9 | ALL | Volume + external agent |
| 6 Ship | M5 | 10 | ALL | Final resubmission |

**Critical path:** Phase 1 → everything. If M0 slips, the plan slips; CC-A does nothing else until it's green, CC-B works the mock rail in parallel so a slow M0 never idles the team.
