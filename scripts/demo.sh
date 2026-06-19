#!/usr/bin/env bash
# Zero-fund local demo: starts the agent, runs a few queries through the full citation
# loop (mock rail), and prints the traction metrics. Lets a reviewer see Keryx work
# end-to-end without any testnet funds. For real on-chain settlement see rail/m0_spike/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
PORT="${PORT:-8000}"
URL="http://127.0.0.1:${PORT}"

[ -x "$PY" ] || { echo "Create the venv first: python3.11 -m venv .venv && .venv/bin/pip install -e '.[dev]'"; exit 1; }

echo "[demo] starting agent on ${URL} ..."
"$ROOT/.venv/bin/uvicorn" agent.main:app --port "$PORT" >/tmp/keryx_demo_agent.log 2>&1 &
AGENT_PID=$!
trap 'kill $AGENT_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 40); do
  curl -fs "${URL}/healthz" >/dev/null 2>&1 && break
  sleep 0.3
done

echo "[demo] asking a question (full citation loop, mock rail) ..."
curl -s -X POST "${URL}/ask" -H 'content-type: application/json' \
  -d '{"query":"How do Gateway nanopayments settle sub-cent USDC on Arc?"}' \
  | "$PY" -m json.tool

echo "[demo] generating a little volume (team + external) ..."
"$PY" -m agent.fleet --url "$URL" --n 6 >/dev/null
"$PY" -m agent.fleet --url "$URL" --n 4 --external >/dev/null

echo "[demo] traction metrics:"
curl -s "${URL}/metrics" | "$PY" -m json.tool

echo "[demo] done. For the live dashboard: cd web && pnpm dev  (then open http://localhost:3000)"
