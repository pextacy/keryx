# Keryx public backend — runs the whole real-rail settlement path in one container:
#   seller.ts (x402 citation toll) + payer.ts (Gateway bridge) + the FastAPI agent.
# The agent settles real test-USDC on Arc testnet through the local rail (KERYX_RAIL=http).
# Built for a long-running host (Render/Railway/Fly) — NOT Vercel (serverless can't keep
# the rail services up). The web frontend (Vercel) points AGENT_URL at this service.
FROM python:3.11-slim

# Node 22 for the TypeScript rail (native type-stripping via --experimental-transform-types),
# plus build tools for any Python deps without a wheel.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates build-essential \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps (the agent + shared + rail + registry packages).
COPY pyproject.toml ./
COPY shared ./shared
COPY agent ./agent
COPY registry ./registry
COPY rail ./rail
COPY db ./db
RUN pip install --no-cache-dir .

# TS rail deps.
RUN cd rail/m0_spike && npm install --omit=dev --no-audit --no-fund

COPY start.sh ./
RUN chmod +x start.sh

# Real rail by default; the host supplies BUYER_PRIVATE_KEY + AUTHOR_ADDRESS as secrets.
ENV KERYX_RAIL=http \
    KERYX_NETWORK=testnet \
    PYTHONUNBUFFERED=1

CMD ["./start.sh"]
