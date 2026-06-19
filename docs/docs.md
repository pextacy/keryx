# docs.md

The source map for **Keryx**. We assemble from existing open-source rather than authoring from scratch. For each capability: the repo, its license, the files that matter, our customization delta, and where the live docs are.

> License posture: the user confirms these are permissive (MIT). Regardless, **keep each upstream LICENSE on vendoring, add attribution in a NOTICE, and license our own additions MIT.** Verify the LICENSE file the moment you clone — it's a 5-second check and it ships in the repo we submit.

## Clone & customize

| Capability | Repo | License | Key files / what we take | Our delta |
| --- | --- | --- | --- | --- |
| **Payments rail (core)** | `circlefin/arc-nanopayments` | permissive (verify) | LangChain paying agent, x402-protected seller endpoints, Gateway batching | Customize the seller endpoint → our `/cite` citation toll; reuse the paying-agent x402 client + Gateway batching as-is |
| Rail reference / explainer | `the-canteen-dev/circle-agent` | permissive (verify) | Worked example of the full stack | Read for patterns; lift wiring, not product |
| Dev tooling + testnet RPC | `the-canteen-dev/ARC-cli` | permissive (verify) | `arc-canteen` CLI: RPC, context sync, submit, dashboard | Use directly; don't fork |
| Arc/Circle agent context | `the-canteen-dev/context-arc` | permissive (verify) | Bundled docs + 5 sample codebases (submodules); `AGENTS.md` | Pull via `arc-canteen context sync`; feed to both Claude Codes |
| Wallets + x402 payments + faucet | Circle CLI `@circle-fin/cli` | permissive (verify) | Agent + author wallet provisioning, x402-compatible payments, testnet faucet | Provision wallets via CLI/SDK; follow `arc-nanopayments` for the canonical signing path |
| Source ingest | `DIYgod/RSSHub` | MIT | `DataItem.link` (canonical URL) + `DataItem.author` | Run an instance or hit a hosted one; read items → `registry` (author→wallet) + `sources` cache |
| Agent framework | LangChain | MIT | Agent loop, retrieval, tool use | The `arc-nanopayments` paying agent is already LangChain; extend it |
| Grounding similarity | pgvector on Neon | PostgreSQL (permissive) | Vector store colocated with our Postgres | Embed answer spans + source passages; cosine similarity feeds the grounding score |
| Chain reads (dashboard) | viem | MIT | Read Arc settlement state | Power `GET /ledger` from chain, not the index |
| Surface | Next.js + Tailwind (+ shadcn/ui optional) | MIT | Ask page + live ledger | Build `web/`; deploy on Vercel |

Other Circle Arc sample apps (`arc-p2p-payments`, `arc-commerce`, `arc-multichain-wallet`, `arc-escrow`, …) are reference only — useful for gasless/P2P and wallet patterns if we get stuck, but `arc-nanopayments` is the one we build on.

## Where our original work lives

Not in the table above. Two modules:
- `agent/grounding/` — similarity + LLM-judge → grounding score `g`; gate at `T`; weighted per-citation amount. The moat + the innovation score.
- `agent/attestation/` — the signed citation attestation; the audit trail behind every payment.
- (and the customization of the forked seller into `rail/cite/`.)

## Live docs to pull

- Nanopayments (Gateway): `developers.circle.com/gateway/nanopayments`
- Arc developer docs: `docs.arc.network`
- Agent Stack / Circle CLI: `developers.circle.com/agent-stack/circle-cli`
- ARC-cli docs (Canteen testnet): `arc-node.thecanteenapp.com`
- x402: end-to-end shown in the `arc-nanopayments` reference
- LLMs.txt (agent context): `developers.circle.com/llms.txt`

Always verify x402 headers, the Gateway batch-submit shape, and EIP-3009 fields against the live docs + the `arc-nanopayments` source at M0 — don't trust any signature reproduced from memory in these planning files.

## Clone order (day 1)

```
git clone https://github.com/circlefin/arc-nanopayments
git clone https://github.com/the-canteen-dev/circle-agent
arc-canteen context sync          # pulls context-arc: docs + 5 sample codebases
# RSSHub: run a local instance or point at a hosted one
```
Then: confirm LICENSE on each, wire `.env`, and drive M0 — one test-USDC nanopayment clears before anything else.
