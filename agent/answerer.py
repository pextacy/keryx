"""Answer generation — pluggable, with an offline default.

Production uses the LangChain paying agent (an LLM) to synthesize an answer from the
retrieved sources. For CI/offline we ship an ``ExtractiveAnswerer`` that composes the
answer from the most query-relevant source sentences — deterministic and dependency-free
— behind an ``Answerer`` protocol so the LLM answerer drops in unchanged.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agent.grounding.embeddings import similarity
from registry.models import Source


@runtime_checkable
class Answerer(Protocol):
    def answer(self, query: str, sources: list[Source]) -> str: ...


class ExtractiveAnswerer:
    """Compose an answer from the source sentences most relevant to the query."""

    def __init__(self, max_sentences: int = 4) -> None:
        self.max_sentences = max_sentences

    def answer(self, query: str, sources: list[Source]) -> str:
        sentences: list[str] = []
        for s in sources:
            for part in s.text.replace("\n", " ").split("."):
                p = part.strip()
                if p:
                    sentences.append(p)
        if not sentences:
            return "No sources available to answer the question."
        ranked = sorted(sentences, key=lambda snt: similarity(query, snt), reverse=True)
        chosen = ranked[: self.max_sentences]
        # Preserve original order among the chosen for readability.
        ordered = [s for s in sentences if s in set(chosen)][: self.max_sentences]
        return ". ".join(ordered) + "."
