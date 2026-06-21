# vendor/circle — Circle open-source repos (vendored in-tree)

These are Circle's (`github.com/circlefin`) public, permissively-licensed repos, cloned and
vendored here for reference and reuse. Each keeps its own `LICENSE` (mostly Apache-2.0); their
`.git` history was removed. Attribution is in the repo root [`NOTICE`](../../NOTICE).

We do **not** reimplement what these provide — we build over them. Keryx's original delta lives
in `agent/grounding`, `agent/attestation`, `rail/cite`, and the nanopayment primitives in
`agent/main.py`; these vendored repos are the patterns/SDKs that delta sits on.

| Repo | What it gives Keryx |
| --- | --- |
| `arc-nanopayments` | the rail base — gasless USDC nanopayments via x402 + Gateway on Arc |
| `arc-escrow` | AI-validated escrow workflow — pattern for ERC-8183 escrow-backed bonds |
| `arc-stablecoin-fx` | USDC↔EURC FX via the App Kit Swap SDK |
| `arc-p2p-payments` | gasless P2P payment patterns |
| `arc-commerce` | USDC as a payment method (credits/checkout) |
| `arc-multichain-wallet` | unified USDC balance + crosschain (Gateway) UX |
| `arc-fintech` | multichain treasury / crosschain capital movement |
| `recibo` | encrypted memos for ERC-20 — the basis for our memo'd `/send` + provenance |
| `refund-protocol` | stablecoin payment disputes — the basis for our `/refund` flow |
| `circle-ooak` | Object-Oriented Agent Kit (Python) — agent patterns |
| `agent-stack-starter-kits` | Circle Agent Stack examples (LangChain, Claude Agent SDK, …) |

Excluded from the project's build/lint/test: `vendor/` is outside the `ruff`/`mypy`/`tsc`
include paths and `pytest` testpaths, so vendoring these does not affect Keryx's gates.
