"""Rail FastAPI app (CC-A).

Run: ``uvicorn rail.main:app --reload``

Phase 0 scope: a runnable, importable app with health + config introspection only.
The x402-protected ``/cite`` flow, ``/agent/session``, Gateway batching, and the
``settle()`` interface arrive in Phase 2 (M1) / Phase 3 (M2).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from shared.config import settings

app = FastAPI(
    title="Keryx Rail",
    version="0.0.0",
    summary="x402 seller + Gateway settlement on Arc (CC-A)",
)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"status": "ok", "service": "rail"}


@app.get("/config")
def config() -> dict[str, Any]:
    """Non-secret config echo — confirms settlement economics are wired, not hardcoded."""
    return {
        "usdc_floor": str(settings.usdc_floor),
        "citation_toll_min": str(settings.citation_toll_min),
        "citation_toll_max": str(settings.citation_toll_max),
        "grounding_threshold": settings.grounding_threshold,
        "network": settings.network,
        "arc_chain_id": hex(settings.arc_chain_id),
        "caip2_network": settings.caip2_network,
        "explorer_url": settings.explorer_url,
        "rpc_configured": bool(settings.rpc_url),
    }
