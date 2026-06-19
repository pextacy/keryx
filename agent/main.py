"""Agent FastAPI app (CC-B).

Run: ``uvicorn agent.main:app --reload``

Phase 0 scope: a runnable, importable app wired to the MockRail so the contract is
exercised end-to-end without the real rail. ``POST /ask``, retrieval, the grounding
verifier, and the attestation signer arrive in Phase 2 (M1).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from shared.config import settings
from shared.rail import MockRail, Rail

app = FastAPI(
    title="Keryx Agent",
    version="0.0.0",
    summary="Research agent + grounding verifier + attestation (CC-B)",
)

# Phase 0: depend on the mock rail. Phase 3 swaps this for CC-A's real settle().
rail: Rail = MockRail()


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"status": "ok", "service": "agent", "rail": type(rail).__name__}


@app.get("/config")
def config() -> dict[str, Any]:
    return {
        "grounding_threshold": settings.grounding_threshold,
        "judge_model": settings.judge_model,
        "rsshub_base_url": settings.rsshub_base_url,
        "rail": type(rail).__name__,
    }
