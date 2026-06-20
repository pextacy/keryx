#!/usr/bin/env bash
# Zero-fund capabilities demo: starts the agent, drives every nanopayment primitive with the
# fleet (payout, bonds, streaming, royalties, quadratic funding), and prints the rolled-up
# traction. Lets a reviewer watch real test-USDC volume flow across all primitives in one
# command, no funds needed. The live dashboard for the same data is web /capabilities.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
PORT="${PORT:-8000}"
URL="http://127.0.0.1:${PORT}"
ROUNDS="${ROUNDS:-10}"

[ -x "$PY" ] || { echo "Create the venv first: python3.11 -m venv .venv && .venv/bin/pip install -e '.[dev]'"; exit 1; }

echo "[demo] starting agent on ${URL} ..."
"$ROOT/.venv/bin/uvicorn" agent.main:app --port "$PORT" --log-level warning >/tmp/keryx_cap_demo.log 2>&1 &
AGENT_PID=$!
trap 'kill $AGENT_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 40); do
  curl -fs "${URL}/healthz" >/dev/null 2>&1 && break
  sleep 0.3
done

echo "[demo] driving every primitive for ${ROUNDS} rounds (agents are the users) ..."
"$PY" -m agent.capabilities_fleet --base "$URL" --rounds "$ROUNDS"

echo
echo "[demo] traction (also live at the dashboard) ..."
curl -s "${URL}/traction" | "$PY" -m json.tool

echo
echo "[demo] open the live dashboard:  cd web && pnpm dev  ->  http://localhost:3000/capabilities"
echo "[demo] done."
