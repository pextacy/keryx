# Keryx — Product Requirements

> *Your work earns every time an agent cites it.*
> Citation-toll layer for the agent web: a paying research agent settles a sub-cent USDC nanopayment to every source it genuinely grounds an answer in. Built for the Lepton Agents Hackathon (Canteen × Circle, on Arc).

---

## 1. The problem

The fastest-growing reader of written content is no longer human — it's LLM agents and aggregators, and they read the work as free substrate. The author writes, the model grounds, the answer ships, and no money moves. The reason it never moved is the fee floor: a per-citation payment was always too small to clear. Arc + Gateway removes that floor ($0.000001 USDC, gasless, batched, sub-second). The unit is finally sellable.

Keryx makes a single citation a settling event.

## 2. What we're optimizing for (the rubric)

This is a recruiting/funding funnel disguised as a hackathon — the "we keep going too" line is the tell. Judging is async, resubmittable, and weighted:

| Axis | Weight | How Keryx scores |
| --- | --- | --- |
| Agentic Sophistication | 30% | The agent *decides*: which sources to pull, whether each actually grounded the answer, how much to pay, when budget is spent, which sources to trust next. Not a meter. |
| Traction | 30% | **The users are agents, not humans.** We generate genuine high-volume settlement without recruiting a creator community in 10 days. This is the whole strategic bet. |
| Circle tool usage | 20% | x402 + Gateway Nanopayments + Wallets + USDC on Arc. The canonical showcase; we fork the reference impl. |
| Innovation | 20% | The attribution layer that *proves* a source grounded an answer (settle on citation, not on fetch). "The payment is the easy part; the real build is attribution." |

Keryx is centered on **RFB 6 (Creator & Publisher Monetization)** — the favored round — and spans **RFB 1 (Autonomous Paying Agents)** and **RFB 3 (Agent-to-Agent Networks)**.

## 3. Goals & non-goals

**Goals (P0)**
- A paying research agent that autonomously answers a query, grounds the answer, and settles per genuinely-cited source on Arc in test USDC.
- A verifiable attribution model that gates payment on real grounding (fetched-but-unused → $0).
- A live public page: ask → research → answer with inline citations → real-time USDC nanopayments to author wallets → live settlement ledger.
- Genuine settlement volume during the event window, including third-party (non-team) queries.

**Non-goals (explicitly out of scope for 10 days)**
- Mainnet / real money. Testnet USDC only.
- Recruiting human creator communities or shipping the full RSSHub-operator product. We ingest a curated source set + expose an open endpoint.
- Full sybil-resistance / on-chain reputation (note as future, ties to ERC-8004).
- Multi-rail. Arc + USDC only.
- Perfect grounding. A v1 heuristic + LLM judge is acceptable and defensible.

## 4. Users

1. **Paying research agent** (primary "user"). Holds a funded wallet, a budget, and per-source caps. Decides what to read, what genuinely grounded the answer, and what to pay.
2. **Source author / publisher** (the paid party). Has a wallet in our registry. Earns per citation. The registry is the moat.
3. **Human asking a question** (the demo surface). Hits the public page, watches authors get paid live.
4. **Other builders' agents** (traction multiplier). Call our open endpoint; the Discord crowd is a willing testnet user base.

## 5. How it works — the citation loop

1. A query arrives (from our page, our agent fleet, or an external agent).
2. The agent retrieves candidate sources (ingested via RSSHub `DataItem.link` + `author`).
3. The agent generates an answer.
4. **Grounding verifier** scores how much each candidate source materially supported the answer.
5. For each source above the grounding threshold, the agent settles a citation toll via x402 → Gateway batches → Arc.
6. The agent emits a **signed attestation** mapping answer → cited sources → amounts → tx hashes.
7. The dashboard reads the **chain** (canonical ledger) and renders live.

Payment is on *citation*, not on *fetch*. A source retrieved but not grounded is logged "evaluated, not cited" at $0 — the play-gating analog to "a skip in the first 30 seconds costs nothing."

## 6. The attribution model (the moat — spec)

For each candidate source against the produced answer:
- **Similarity signal**: semantic similarity between answer spans and source passages.
- **Judge signal**: an LLM judge returns `supported | partial | unsupported` per claim, with a short rationale.
- **Grounding score** `g ∈ [0,1]` combines both.
- **Settlement gate**: pay only if `g ≥ T` (start `T = 0.5`, tunable).
- **Amount**: flat per-citation floor, optionally scaled by `g` so a source that grounded more earns more (an innovation hook — the recursive/weighted-split idea).
- **Attestation**: signed object `{query_hash, answer_hash, [{source_url, g, amount, tx_hash}], agent_pubkey, ts}`. This is verifiable citation — the centerpiece of the innovation story and the audit trail behind every payment.

Demo requirement: the UI must show at least one *evaluated-but-not-cited* source per answer so the gating is visible and the model reads as honest, not pay-to-fetch.

## 7. Settlement model

- **x402** mediates the citation. The agent requests a citation receipt for a source; the seller endpoint returns `402` with payment requirements; the agent retries with a signed **EIP-3009** authorization in the payment header; the seller verifies and accepts.
- **Gateway** aggregates accepted authorizations and settles them on Arc in bulk (gasless, batched).
- **Arc is the ledger.** Settlement clears on-chain; the dashboard reads chain state. No off-chain DB is the source of truth for payments — "don't trust our DB, here's the chain." Off-chain Postgres is only a fast read-index + registry + cache.
- Floor: `$0.000001` USDC. Per-citation toll set well above floor but sub-cent (e.g. `$0.001–$0.01`), tunable per source.

*All exact API signatures (x402 headers, Gateway batch submit, EIP-3009 fields) are verified against `circlefin/arc-nanopayments` and live Circle/Arc docs at build time — see plan.md M0.*

## 8. Success metrics

**North star:** total test-USDC settled to author wallets during the event window.

Supporting (the traction story we'll point judges at):
- Distinct author wallets paid
- Distinct paying agent sessions
- Citations settled (count)
- **% of queries from non-team / external agents** — the credibility signal
- Queries/day trend

**Targets to beat by submission** (adjustable): 1,000+ citations settled · 50+ distinct author wallets paid · ≥1 external agent integration + meaningful Discord usage. The dashboard labels team vs external volume transparently — self-generated agent volume is legitimate (agents *are* the users) but external usage is what we lead with.

## 9. Risks

| Risk | Mitigation |
| --- | --- |
| Rail integration friction on Canteen testnet | Fork the reference repo; **one test-USDC nanopayment must clear before anything is built on top** (M0 gate). Keep a mock rail so the agent workstream is never blocked. |
| Grounding verifier reads as hand-wavy | Invest in the signed attestation + visibly show skip-gating (evaluated-but-not-cited). |
| Traction reads as self-dealing | Genuinely open the endpoint to Discord; label team vs external volume in the dashboard. |
| Gateway/x402 testnet quirks | Daily integration sync; mock rail fallback; verify against live docs early. |

## 10. Deliverables (submission)

- **Public GitHub repo** — required. Built for a reviewer clicking around without us in the room.
- **Video demo** — required, <3 min (Loom/YouTube/Vimeo): ask → research → inline citations → live payments → ledger.
- **Live deployed link** — strongly encouraged; we ship it.
- **Traction answers**: users/agents onboarded, problems solved.
- Submit via the form **early and often** (resubmission allowed; submit a v1 around day 7).
