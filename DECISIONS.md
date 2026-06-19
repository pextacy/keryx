# Decisions & Open Questions

Running log of choices and unresolved questions surfaced during the build. Phase 0
entries first.

## RESOLVED (2026-06-19) — Rail in TypeScript, agent in Python, bridged over the frozen contract → Option (A)

**Decision:** The x402 + Gateway batching SDK (`@circle-fin/x402-batching`, both the
`BatchFacilitatorClient` server and the `GatewayClient` payer) is **TypeScript-only** —
there is no Python equivalent. Per "assemble, don't author," the rail stays TS:
- `rail/m0_spike/seller.ts` → the `/cite` seller (verify → settle).
- `rail/payer/` → a tiny TS service wrapping `GatewayClient.pay()` per `CitationIntent`.
- The Python agent settles via `shared.rail.HttpRail`, which POSTs intents to the payer
  and gets back `Receipt`s — the same frozen `settle(intents) -> list[Receipt]` contract,
  so the agent code is identical whether it talks to `MockRail` or the real rail.

The moat (grounding + attestation) stays Python. This is provisional engineering driven
by the SDK constraint; the user/CC-A owner can override. Original OPEN analysis kept below.

### OPEN (superseded) — Rail language: Python/FastAPI (planned) vs TypeScript (actual upstream)

**Discovered (2026-06-19, Phase 0 vendoring):** `circlefin/arc-nanopayments` — the
repo `plan.md`/`docs.md` tell us to fork and "stay on" — is a **TypeScript / Next.js**
app built on **`@langchain/core` (LangChain.js)** + **viem**, licensed **Apache-2.0**.
The planning docs assumed Python/FastAPI + Python LangChain ("the arc-nanopayments
paying agent is already LangChain; extend it").

**Implication:** "Assemble, don't author" (the #2 ground rule) points to reusing the
upstream x402 client + Gateway batching **as-is in TypeScript**. Building `rail/` in
Python would mean re-authoring the canonical signing/batching path — exactly what the
rules say not to do.

**Options:**
- **(A) Rail in TS** matching upstream (reuse x402/Gateway directly); keep `agent/`
  grounding+attestation in Python (the moat is ours either way), bridged over the
  frozen `shared/` HTTP contract. Lowest re-authoring risk.
- **(B) Everything Python/FastAPI** as `plan.md` states; port the x402/Gateway client
  to Python (more original code on the rail, against the assemble rule).
- **(C) Everything TS** matching upstream end-to-end.

**Status:** Needs the user / CC-A owner. Does **not** block Phase 0 — the `shared/`
contract is language-agnostic in shape and the Python scaffold follows the documented
plan. Resolve before Phase 2 (M1), since it decides what `rail/` is written in.

## RESOLVED (2026-06-19) — Grounding moat runs on Claude, with an offline fallback

**Decision:** The grounding judge and answer synthesis are now real Claude calls, not
just the lexical heuristic. `AnthropicJudge` (`agent/grounding/judge.py`) asks
`claude-opus-4-8` for per-claim `supported|partial|unsupported` verdicts via structured
outputs (adaptive thinking, effort-tunable); `AnthropicAnswerer` (`agent/answerer.py`)
synthesizes the answer from retrieved sources. Both sit behind the existing
`Judge`/`Answerer` protocols and are selected by `agent/factory.py`:
- `KERYX_ANTHROPIC_API_KEY` set → Claude path (the production moat).
- unset → the deterministic offline heuristics (CI/demo default — no network, reproducible).

Both LLM classes **degrade to the heuristic on any API error**, so a key/quota/network
problem never breaks the citation loop; the grounding rationale records which judge
actually decided (`[claude:…]` vs `[fallback:heuristic]`). `/config` and `/healthz`
report the live mode. Models/effort/max-tokens are config (`KERYX_*`), never hardcoded.
The remaining grounding swap is dense-embedding similarity (pgvector); the TF-cosine
similarity signal stays as the documented v1.

## RESOLVED (2026-06-20) — On-chain attribution layer (`contracts/`), settlement stays on Circle Gateway

**Decision:** Added an optional on-chain attribution layer under `contracts/` (Foundry,
Solidity 0.8.24) that puts the moat on-chain: an **ERC-8004-inspired triad**
(`IdentityRegistry` / `ReputationRegistry` / `ValidationRegistry`), a signed-attestation
log (`CitationRegistry`, EIP-712 verify + replay guard), on-chain economics (`KeryxToll`,
mirrors `shared/config.py`), a weighted **`CitationSplitter`** (the recursive/weighted-split
innovation), and a `KeryxSettlement` orchestrator that enforces *pay-on-citation* (g < T
reverts). 18 forge tests green; deploy script + CI job added. PRD §3/§6 flagged ERC-8004
reputation and weighted split as innovation/future — this realizes them.

**USDC settlement still clears through Circle Gateway** (pre-deployed on Arc, `0x0077…19B9`).
We do **not** reimplement x402/Gateway (ground rule #1). These contracts are the *attribution*
layer alongside that rail, not a replacement for it.

**On count:** the right number of contracts is driven by responsibility, not a target. A
request for "100–150 contracts" (or one-per-author) is an EVM anti-pattern — all authors are
rows in **one** `IdentityRegistry` mapping (`test_identity_scales_to_200_authors` proves 200
identities in a single contract). The suite is 7 contracts + 3 interfaces + 3 libraries +
`Owned` + a test `MockUSDC` (15 source units). Deploying hundreds of contracts would multiply
gas/deploy cost with zero benefit; no serious protocol does it.

## NOTED — arc-nanopayments ships a `supabase/` directory

Upstream uses Supabase; our ground rules forbid Supabase anywhere (use Neon). When we
fork the seller endpoint we must strip/replace the Supabase data layer with Neon. Flagged
so it isn't carried in by accident during the Phase 2 fork.

## DONE — Settlement amounts as config

Floor `$0.000001`, toll `$0.001–$0.01`, `T=0.5` live in `shared/config.py` (env-driven,
`KERYX_*`), never hardcoded. Per CLAUDE.md.

## DONE — `shared/` types frozen

`CitationIntent`, `Receipt`, `Attestation` are `frozen=True` Pydantic models with strict
validation. Changes are coordinated, not unilateral.
