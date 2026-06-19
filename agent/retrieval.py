"""Retrieval — pick candidate sources for a query.

Ranks the source cache by similarity to the query and returns the top-k candidates.
Deliberately over-retrieves: some candidates will be evaluated and *not* cited, which
is the visible gating prd.md requires. Production swaps in pgvector ANN; the interface
is the same.
"""

from __future__ import annotations

from agent.grounding.embeddings import Embedder, similarity
from registry.models import Source
from registry.store import SourceStore


def retrieve(
    query: str, store: SourceStore, *, k: int = 5, embedder: Embedder | None = None
) -> list[Source]:
    scored = [(similarity(query, f"{s.title}. {s.text}", embedder), s) for s in store.all()]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:k]]
