#!/usr/bin/env bash
# Launch the full real-rail path in one container: seller + payer (internal, on their
# default localhost ports) then the FastAPI agent on the host's $PORT (public).
# The agent settles via KERYX_RAIL=http -> payer (localhost:3403) -> seller
# (localhost:3402) -> Circle Gateway on Arc testnet.
set -euo pipefail

NODE_FLAGS="--experimental-transform-types --no-warnings"

echo "[start] launching seller (x402 toll) on :3402"
( cd /app/rail/m0_spike && node $NODE_FLAGS seller.ts ) &

echo "[start] launching payer (Gateway rail bridge) on :3403"
( cd /app/rail/m0_spike && node $NODE_FLAGS payer.ts ) &

# Give the rail a moment to bind before the agent accepts traffic.
sleep 3

echo "[start] launching agent (FastAPI, KERYX_RAIL=$KERYX_RAIL) on :${PORT:-8000}"
exec uvicorn agent.main:app --host 0.0.0.0 --port "${PORT:-8000}"
