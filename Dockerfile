# Keryx agent (FastAPI/uvicorn) — the Python service. Web is a separate Next.js app (web/).
FROM python:3.11-slim

WORKDIR /app

# Install the package + runtime deps (psycopg[binary], eth-account, etc. are wheels).
COPY pyproject.toml ./
COPY shared ./shared
COPY rail ./rail
COPY agent ./agent
COPY registry ./registry
RUN pip install --no-cache-dir .

# Offline-safe defaults: no DB/RPC/LLM/keys required to boot. Set KERYX_* to enable features.
ENV PORT=8000
EXPOSE 8000

# Render/most PaaS inject $PORT; default 8000 for local `docker run`.
CMD ["sh", "-c", "uvicorn agent.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
