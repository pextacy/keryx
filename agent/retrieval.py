"""Retrieval — pick candidate sources for a query.

Ranks the source cache by similarity to the query and returns the top-k candidates.
Deliberately over-retrieves: some candidates will be evaluated and *not* cited, which
is the visible gating prd.md requires. Production swaps in pgvector ANN; the interface
is the same.
"""

from __future__ import annotations

from agent.grounding.embeddings import BagOfWordsEmbedder, Embedder, cosine
from registry.models import Source
from registry.store import SourceStore


def retrieve(
    query: str, store: SourceStore, *, k: int = 5, embedder: Embedder | None = None
) -> list[Source]:
    """Rank sources by similarity to the query and return the top-k candidates.

    Embeds the query and every candidate in ONE batched call (``embed_many``), and embeds
    each source as ``s.text`` — the same canonical string the scorer uses — so a source is
    embedded once across retrieval and grounding (shared instance + cache). With
    ``embedder=None`` this is the deterministic offline BagOfWords path.
    """
    sources = list(store.all())
    if not sources:
        return []
    emb = embedder or BagOfWordsEmbedder()
    vectors = emb.embed_many([query, *(s.text for s in sources)])
    q_vec = vectors[0]
    scored = [(cosine(q_vec, vectors[i + 1]), s) for i, s in enumerate(sources)]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:k]]
