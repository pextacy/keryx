# Keryx — Lepton Hackathon submission kit

Turnkey package: the live links, a <3-min video script you just read aloud while
clicking, and copy-paste answers for the submission form.

## Links (paste into the form)
- **Live product:** https://keryx-soag.vercel.app
- **GitHub repo:** https://github.com/pextacy/keryx
- **Backend (real Arc-testnet settlement):** https://keryx-backend-5dwf.onrender.com
- **Video:** _(record with the script below, upload to Loom/YouTube, paste link)_

> ⚠️ Before recording / before judges click: hit the live link once to wake the
> free backend (~50s cold start), then it's instant.

## One-line pitch
**Your work earns every time an agent cites it.** A paying research agent answers a
query, proves which sources actually grounded its answer, and settles a sub-cent USDC
nanopayment to each cited author on Arc — pay on *citation*, not on *fetch*. A source
that was read but didn't ground the answer earns **$0, visibly**.

---

## 🎬 Video script (< 3 minutes — read aloud while you click)

**[0:00–0:20] The problem**
> "AI agents read the whole web as free substrate. The reporter who files a story
> earns nothing when a thousand answers are grounded in it. Keryx fixes that: agents
> pay authors a sub-cent USDC toll every time they actually cite them — on Arc."

**[0:20–1:15] The live citation loop** — open https://keryx-soag.vercel.app
> "I ask a real question." → type *"How do Gateway nanopayments settle sub-cent USDC on Arc?"* → Ask.
> "The agent retrieves sources, writes an answer, and a grounding verifier scores how
> much each source supported the answer. Watch: these two sources grounded the answer —
> they get **paid**, in real test-USDC on Arc. This off-topic source was read but didn't
> ground anything — it earns **$0**. That's the whole thesis: pay on citation, not fetch."
> Click a settled citation's tx → show it resolves (Circle Gateway transfer on Arc).

**[1:15–2:00] It's a full nanopayment suite** — open `/capabilities`
> "Beyond citation tolls, Keryx exposes 21 sub-cent primitives — royalty splits,
> reputation bonds, per-second streaming, quadratic funding — each settling real
> test-USDC through Circle's Gateway." → open the **Royalty split** panel, run it →
> "One payment, split across contributors down to the micro-USDC, dust-free, on-chain."
> Open `/ledger` → "Here's the live settled volume accumulating."

**[2:00–2:40] The tech (Circle + agency)**
> "Settlement is x402 + Circle Gateway batching, native USDC gas on Arc — sub-cent
> clears for the first time. The agent decides everything: what to retrieve, what to
> answer, and — the moat — a per-claim grounding judge that gates every payment. We
> also ported 14 of Circle's open-source Arc repos into the same rail."

**[2:40–3:00] Traction + close**
> "Agents are the users here — they're paying each other in test-USDC right now; the
> volume is on the live `/traction` feed. Make the smallest unit of value sellable.
> Keryx: your work earns every time an agent cites it."

---

## 📝 Form answers (copy-paste)

**What did you build?**
> Keryx is a citation-toll layer for the agent web. A paying research agent answers a
> query, a grounding verifier proves which sources actually grounded the answer (per-claim
> LLM judge + similarity), and it settles a sub-cent USDC nanopayment to each cited author
> on Arc via x402 + Circle Gateway batching. Payment is on citation, not fetch — a source
> read but not grounded earns $0, visibly. It also exposes 21 nanopayment primitives
> (royalty splits, reputation bonds, per-second streaming, quadratic funding) and ports 14
> of Circle's open-source Arc repos onto the same rail.

**Who are your users / how much traction?**
> Agents are the users — this is an agent-to-agent nanopayment network. During the event,
> **~0.33 USDC settled across 81 real Circle Gateway transfers on Arc testnet** — 31
> citation tolls (agent → cited author) plus 50 primitive payments (royalty splits,
> reputation bonds, quadratic-funding matches, per-second streams). All live and pointable
> at https://keryx-soag.vercel.app/ledger and the `/traction` feed — real transfers, not
> mocks. (Volume keeps growing each time the agent runs.)

**What user problem are you solving?**
> Creators and publishers earn nothing when AI agents ground answers in their work — the
> payment floor (~30¢ after fees) made per-citation payment impossible. Keryx removes the
> floor: at Circle Gateway's $0.000001 minimum, a single citation is finally worth settling,
> so authors get paid per use, automatically, in the proportions attribution already records.

**How did you use Circle's tools?**
> x402 (HTTP 402 pay-per-request on the seller's /cite endpoint), Circle Gateway +
> Nanopayments (gasless batched USDC settlement, the real rail), USDC on Arc (native gas,
> sub-second finality), agent wallets, and 14 ported Circle open-source Arc repos
> (arc-commerce, arc-escrow, arc-stablecoin-fx, arc-p2p-payments, …).

## Why it scores
- **Agentic (30%)** — the agent decides retrieval + synthesis, and a per-claim grounding
  judge (the moat) gates every payment. Off-topic earns $0 autonomously.
- **Traction (30%)** — real test-USDC flowing agent→author + across 21 primitives, live.
- **Circle tools (20%)** — x402 + Gateway + USDC on Arc end to end, plus 14 repo ports.
- **Innovation (20%)** — pay-on-citation (not fetch), provable grounding as the payout
  rule, quadratic funding + reputation bonds + streaming for content.

## Submission checklist
- [ ] Register on Luma + correct GitHub/Discord handles
- [ ] Join Canteen + Arc builder Discords
- [ ] Wake the live backend right before recording (cold start)
- [ ] Record the 3-min video → upload → paste link
- [ ] Submit the form (resubmit freely — submit early)
- [ ] (after) rotate the BUYER wallet key + Neon password (both leaked in dev chat)
