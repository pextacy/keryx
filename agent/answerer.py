"""Answer generation — pluggable, with an offline default.

Production uses the LangChain paying agent (an LLM) to synthesize an answer from the
retrieved sources. For CI/offline we ship an ``ExtractiveAnswerer`` that composes the
answer from the most query-relevant source sentences — deterministic and dependency-free
— behind an ``Answerer`` protocol so the LLM answerer drops in unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from agent.grounding.embeddings import similarity
from registry.models import Source

if TYPE_CHECKING:
    from anthropic import Anthropic

log = logging.getLogger("keryx.answerer")


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


_ANSWER_SYSTEM = (
    "You are a research agent. Answer the user's question using ONLY the provided "
    "sources. Be concise and factual — a few sentences. Ground every claim in the "
    "sources; do not add outside knowledge. If the sources do not contain the answer, "
    "say so plainly. Do not cite source numbers or add preamble — just give the answer."
)


class AnthropicAnswerer:
    """Claude-backed answer synthesis from retrieved sources (prd.md §5 step 3).

    Falls back to ``ExtractiveAnswerer`` on any API failure so the citation loop never
    breaks. Source text is truncated per-source to keep the prompt bounded.
    """

    def __init__(
        self,
        client: Anthropic,
        *,
        model: str,
        effort: str = "medium",
        max_tokens: int = 4096,
        per_source_chars: int = 2000,
        fallback: Answerer | None = None,
    ) -> None:
        self._client = client
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.per_source_chars = per_source_chars
        self.fallback: Answerer = fallback or ExtractiveAnswerer()

    def answer(self, query: str, sources: list[Source]) -> str:
        if not sources:
            return "No sources available to answer the question."
        blocks = "\n\n".join(
            f"[{i + 1}] {s.title}\n{s.text[: self.per_source_chars]}" for i, s in enumerate(sources)
        )
        client: Any = self._client  # SDK call is an untyped boundary; guarded by except
        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort},
                system=_ANSWER_SYSTEM,
                messages=[{"role": "user", "content": f"Question: {query}\n\nSources:\n{blocks}"}],
            )
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            if not text:
                raise ValueError("empty answer from model")
            return text
        except Exception as exc:  # noqa: BLE001 — degrade to the offline answerer
            log.warning("AnthropicAnswerer fell back to extractive: %s", exc)
            return self.fallback.answer(query, sources)
