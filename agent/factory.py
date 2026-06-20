"""Build the agent's grounding + answering components from settings.

One decision point for the whole agent: when an Anthropic API key is configured the
real Claude judge + answerer are used (the production moat), and when a Voyage key is
set the dense embedder powers the similarity signal; otherwise the offline heuristics.
Everything downstream (scorer, pipeline) is identical either way.
"""

from __future__ import annotations

from agent.answerer import Answerer, AnthropicAnswerer, ExtractiveAnswerer
from agent.grounding.embeddings import Embedder, VoyageEmbedder
from agent.grounding.judge import AnthropicJudge, HeuristicJudge, Judge
from agent.grounding.scorer import GroundingScorer
from agent.llm import get_client
from shared.config import Settings
from shared.config import settings as default_settings


def build_embedder(config: Settings | None = None) -> Embedder | None:
    """Dense Voyage embedder when ``KERYX_VOYAGE_API_KEY`` is set, else ``None``.

    ``None`` means downstream falls back to the offline BagOfWords default (so CI and
    zero-config demos stay deterministic and dependency-free), mirroring the LLM path.
    """
    cfg = config or default_settings
    if not cfg.voyage_api_key:
        return None
    return VoyageEmbedder(
        cfg.voyage_api_key,
        model=cfg.embedding_model,
        connect_timeout=cfg.embedding_connect_timeout,
        read_timeout=cfg.embedding_read_timeout,
        max_retries=cfg.embedding_max_retries,
        backoff_base=cfg.embedding_backoff_base,
        backoff_cap=cfg.embedding_backoff_cap,
        batch_size=cfg.embedding_batch_size,
        cache_size=cfg.embedding_cache_size,
        max_input_chars=cfg.embedding_max_input_chars,
        dimensions=cfg.embedding_dimensions,
    )


def build_judge(config: Settings | None = None) -> Judge:
    cfg = config or default_settings
    client = get_client(cfg)
    if client is None:
        return HeuristicJudge()
    return AnthropicJudge(
        client,
        model=cfg.judge_model,
        effort=cfg.judge_effort,
        max_tokens=cfg.llm_max_tokens,
    )


def build_answerer(config: Settings | None = None) -> Answerer:
    cfg = config or default_settings
    client = get_client(cfg)
    if client is None:
        return ExtractiveAnswerer()
    return AnthropicAnswerer(
        client,
        model=cfg.answer_model_resolved,
        effort=cfg.answer_effort,
        max_tokens=cfg.llm_max_tokens,
    )


def build_scorer(
    config: Settings | None = None, *, embedder: Embedder | None = None
) -> GroundingScorer:
    cfg = config or default_settings
    # Share the caller's embedder when given (one instance -> one cache across scoring +
    # retrieval); otherwise derive from config (Voyage if keyed, else BagOfWords default).
    emb = embedder if embedder is not None else build_embedder(cfg)
    return GroundingScorer(config=cfg, embedder=emb, judge=build_judge(cfg))
