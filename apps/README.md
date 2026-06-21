# apps/ — Circle's open-source Arc apps, adopted into Keryx

These are Circle's (`github.com/circlefin`) public, permissively-licensed projects, **adopted
in-tree as standalone apps** that are part of Keryx — not reimplemented, not bridged over HTTP.
Each keeps its own `LICENSE` (mostly Apache-2.0); their upstream `.git` history was removed.
Attribution is in the repo-root [`NOTICE`](../NOTICE).

We build *over* these. Keryx's original delta lives in `agent/grounding`, `agent/attestation`,
`rail/cite`, and the nanopayment primitives in `agent/main.py`; these apps are the patterns/SDKs
that delta sits on. One of them — **`circle-ooak`** — is installed and called **directly,
in-process** by the agent's approved-action workflow (`/workflow/*`).

## Adopted apps

| App | Stack | How it plugs into Keryx |
| --- | --- | --- |
| `circle-ooak` | Python pkg | **Used directly**: its `WorkflowManager` is the real engine behind `/workflow/*` (installed editable, see below) |
| `arc-nanopayments` | Next.js + LangChain | the rail base — gasless USDC nanopayments via x402 + Gateway on Arc (the `rail/` bridge builds on it) |
| `arc-escrow` | Next.js | AI-validated escrow workflow — pattern for ERC-8183 escrow-backed bonds |
| `arc-stablecoin-fx` | Next.js | USDC↔EURC FX via the App Kit Swap SDK |
| `arc-p2p-payments` | Next.js | gasless P2P payment patterns |
| `arc-commerce` | Next.js | USDC as a payment method (credits/checkout) |
| `arc-multichain-wallet` | Next.js | unified USDC balance + crosschain (Gateway) UX |
| `arc-fintech` | Next.js | multichain treasury / crosschain capital movement |
| `agent-stack-starter-kits` | examples | Circle Agent Stack examples (LangChain, Claude Agent SDK, …) |

Circle's Foundry projects are adopted under [`../contracts/vendor/`](../contracts/vendor):
`recibo` (encrypted ERC-20 memos — basis for our memo'd `/send`) and `refund-protocol`
(stablecoin disputes — basis for `/refund`). They build standalone (`make contracts-vendor`).

## Running them

`circle-ooak` is a real Keryx dependency, installed by `make install`:

```bash
pip install -e apps/circle-ooak     # done for you by `make install`
```

The Next.js apps are standalone — each has its own `package.json` and needs its own env
(most use Supabase + Circle Developer-Controlled Wallets + Arc testnet keys; see each app's
`.env.example`). Run one directly:

```bash
cd apps/arc-nanopayments && npm install && npm run dev
```

`make apps-list` prints this registry; `make app-run APP=arc-nanopayments` is a shortcut.

## Build/lint/test scope

`apps/` and `contracts/vendor/` are **outside** Keryx's Python gates (`ruff`/`mypy` exclude
them, `pytest` testpaths don't include them) and outside the root `web/` Next build — they
carry their own toolchains. Adopting them does not change Keryx's own gates. The one exception
is `circle-ooak`, which is imported by the agent and therefore installed and exercised by the
agent's tests (`tests/test_ooak_workflow.py`).
