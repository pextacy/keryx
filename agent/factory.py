"""Build the agent's grounding + answering components from settings.

One decision point for the whole agent: when an Anthropic API key is configured the
real Claude judge + answerer are used (the production moat); otherwise the offline
heuristics. Everything downstream (scorer, pipeline) is identical either way.
"""

from __future__ import annotations

from agent.answerer import Answerer, AnthropicAnswerer, ExtractiveAnswerer
from agent.grounding.judge import AnthropicJudge, HeuristicJudge, Judge
from agent.grounding.scorer import GroundingScorer
from agent.llm import get_client
from shared.config import Settings
from shared.config import settings as default_settings


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


def build_scorer(config: Settings | None = None) -> GroundingScorer:
    cfg = config or default_settings
    return GroundingScorer(config=cfg, judge=build_judge(cfg))
