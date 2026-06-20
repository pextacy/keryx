"""agent/grounding/ — the moat (ORIGINAL WORK).

Similarity (cosine over answer x source) + LLM-judge (supported|partial|unsupported)
-> grounding score g in [0,1]; gate at T; weighted per-citation amount. Pluggable
embedder/judge so the offline v1 (CI-safe) and the production pgvector + LLM judge
share one interface.
"""

from __future__ import annotations

from agent.grounding.embeddings import (
    BagOfWordsEmbedder,
    Embedder,
    VoyageEmbedder,
    cosine,
    similarity,
)
from agent.grounding.judge import AnthropicJudge, HeuristicJudge, Judge, JudgeResult, Verdict
from agent.grounding.scorer import GroundingResult, GroundingScorer

__all__ = [
    "AnthropicJudge",
    "BagOfWordsEmbedder",
    "Embedder",
    "GroundingResult",
    "GroundingScorer",
    "HeuristicJudge",
    "Judge",
    "JudgeResult",
    "Verdict",
    "VoyageEmbedder",
    "cosine",
    "similarity",
]
