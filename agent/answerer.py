"""Answer generation — pluggable, with an offline default.

Production uses the LangChain paying agent (an LLM) to synthesize an answer from the
retrieved sources. For CI/offline we ship an ``ExtractiveAnswerer`` that composes the
answer from the most query-relevant source sentences — deterministic and dependency-free
— behind an ``Answerer`` protocol so the LLM answerer drops in unchanged.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from agent.grounding.embeddings import similarity
from agent.llm import call_with_retry
from registry.models import Source

if TYPE_CHECKING:
    from google.genai import Client as GeminiClient

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
        scored = [(snt, similarity(query, snt)) for snt in sentences]
        best = max(sc for _, sc in scored)
        # Only keep sentences clearly relevant to the query — at least a third as
        # relevant as the best match — so an off-topic candidate source (evaluated
        # but not cited) never leaks into the answer. Always keep the single best
        # sentence even when the query barely matches anything.
        floor = best * 0.35
        ranked = sorted(scored, key=lambda x: x[1], reverse=True)
        passing = [snt for snt, sc in ranked if sc >= floor] or [ranked[0][0]]
        chosen = set(passing[: self.max_sentences])
        # Preserve original order among the chosen for readability.
        ordered = [s for s in sentences if s in chosen][: self.max_sentences]
        return ". ".join(ordered) + "."


_ANSWER_SYSTEM = (
    "You are a research agent. Answer the user's question using ONLY the provided "
    "sources. Be concise and factual — a few sentences. Ground every claim in the "
    "sources; do not add outside knowledge. If the sources do not contain the answer, "
    "say so plainly. Do not cite source numbers or add preamble — just give the answer."
)


class GeminiAnswerer:
    """Gemini-backed answer synthesis from retrieved sources (prd.md §5 step 3).

    Transient errors (429/5xx) are retried with bounded backoff; any remaining API failure
    degrades to ``ExtractiveAnswerer`` so the citation loop never breaks. Source text is
    truncated per-source to keep the prompt bounded.
    """

    def __init__(
        self,
        client: GeminiClient,
        *,
        model: str,
        max_tokens: int = 4096,
        per_source_chars: int = 2000,
        max_retries: int = 0,
        backoff_base: float = 0.5,
        backoff_cap: float = 8.0,
        sleep: Callable[[float], None] = time.sleep,
        fallback: Answerer | None = None,
    ) -> None:
        self._client = client
        self.model = model
        self.max_tokens = max_tokens
        self.per_source_chars = per_source_chars
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self._sleep = sleep
        self.fallback: Answerer = fallback or ExtractiveAnswerer()

    def answer(self, query: str, sources: list[Source]) -> str:
        if not sources:
            return "No sources available to answer the question."
        blocks = "\n\n".join(
            f"[{i + 1}] {s.title}\n{s.text[: self.per_source_chars]}" for i, s in enumerate(sources)
        )
        client: Any = self._client  # SDK call is an untyped boundary; guarded by except
        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                system_instruction=_ANSWER_SYSTEM,
                max_output_tokens=self.max_tokens,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            contents = f"Question: {query}\n\nSources:\n{blocks}"
            resp = call_with_retry(
                lambda: client.models.generate_content(
                    model=self.model, contents=contents, config=config
                ),
                max_retries=self.max_retries,
                backoff_base=self.backoff_base,
                backoff_cap=self.backoff_cap,
                sleep=self._sleep,
            )
            text = (resp.text or "").strip()
            if not text:
                raise ValueError("empty answer from model")
            return text
        except Exception as exc:  # noqa: BLE001 — degrade to the offline answerer
            log.warning("GeminiAnswerer fell back to extractive: %s", exc)
            return self.fallback.answer(query, sources)
