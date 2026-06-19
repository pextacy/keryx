"""agent/grounding/ — the moat (ORIGINAL WORK).

Similarity (pgvector cosine over answer spans x source passages) + LLM-judge
(supported|partial|unsupported per claim) -> grounding score g in [0,1]; gate at
T; weighted per-citation amount. Implemented in Phase 2 (M1). Placeholder in Phase 0.
"""
