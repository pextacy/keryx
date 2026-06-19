"""Similarity signal for grounding — semantic overlap between answer and source.

In production this is pgvector cosine over real embeddings (docs.md). For a runnable,
offline, deterministic v1 we ship a bag-of-words TF cosine behind an ``Embedder``
protocol, so the real embedder drops in later without touching the scorer.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol, runtime_checkable

_WORD = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _WORD.findall(text.lower())


@runtime_checkable
class Embedder(Protocol):
    """Maps text to a sparse term-frequency vector (token -> weight)."""

    def embed(self, text: str) -> dict[str, float]: ...


class BagOfWordsEmbedder:
    """Deterministic, offline TF embedder. Good enough for the similarity signal v1."""

    def embed(self, text: str) -> dict[str, float]:
        counts = Counter(_tokenize(text))
        total = sum(counts.values()) or 1
        return {tok: n / total for tok, n in counts.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity of two sparse vectors, in [0, 1] for non-negative weights."""
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in shared)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def similarity(answer: str, source_text: str, embedder: Embedder | None = None) -> float:
    """Similarity signal in [0,1] between the answer and a candidate source."""
    emb = embedder or BagOfWordsEmbedder()
    return cosine(emb.embed(answer), emb.embed(source_text))
