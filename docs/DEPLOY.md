# Deploy

Keryx is two services: the **agent** (Python/FastAPI, Docker) and the **web** app
(Next.js). Both boot with offline-safe defaults — no DB/RPC/keys required — so you can ship
the demo first, then flip on integrations from env.

## Render (one blueprint, both services)

`render.yaml` deploys `keryx-agent` (Docker) + `keryx-web` (Node).

1. Push to GitHub, then in Render: **New → Blueprint → pick this repo**. Render reads
   `render.yaml` and creates both services on the free plan.
2. The web's `AGENT_URL` is wired to the agent automatically (`fromService`); the proxy
   prepends `https://` to the hostname (`web/lib/proxy.ts`).
3. Health check: the agent uses `/healthz`.

Defaults: `KERYX_RAIL=mock` (zero-fund demo) and `KERYX_RATE_LIMIT_PER_MINUTE=60`. The agent
is reachable at `https://keryx-agent.onrender.com`; the dashboard at
`https://keryx-web.onrender.com/capabilities`.

### Local Docker (agent only)

```bash
docker build -t keryx-agent .
docker run -p 8000:8000 keryx-agent     # -> http://localhost:8000/healthz
```

## Web on Vercel (alternative to keryx-web)

Next.js auto-detects (`web/vercel.json`). In the Vercel project: set **Root Directory** to
`web`, and add env `AGENT_URL=https://<your-agent-host>` (and `AGENT_API_KEY` if you enabled
auth). Then deploy.

## Turning on the real features (env, set in the dashboard)

| Capability | Env to set |
| --- | --- |
| Real settlement | `KERYX_RAIL=http` + run `rail/m0_spike/payer.ts` (needs a funded Arc wallet) |
| API auth | `KERYX_API_KEY` on the agent + `AGENT_API_KEY` (same value) on the web |
| Postgres mirror | `KERYX_DATABASE_URL` (apply `db/migrations/0001..0003`) |
| Chain-verified ledger | `KERYX_LEDGER_VERIFY_CHAIN=true` + `KERYX_RPC_URL` |
| ERC-8004 / ERC-8183 | `KERYX_ERC8004_ENABLED` / `KERYX_ERC8183_ENABLED` + `KERYX_AGENT_PRIVATE_KEY` |
| Claude moat / dense embeddings | `KERYX_ANTHROPIC_API_KEY` / `KERYX_VOYAGE_API_KEY` |
| Circle Wallets | `KERYX_CIRCLE_API_KEY` |

Everything off → deterministic offline demo. See `.env.example` for the full list.
