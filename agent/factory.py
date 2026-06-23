"""Build the agent's grounding + answering components from settings.

One decision point for the whole agent: when a Gemini API key is configured the real
Gemini judge + answerer are used (the production moat), and when a Voyage key is set the
dense embedder powers the similarity signal; otherwise the offline heuristics. Everything
downstream (scorer, pipeline) is identical either way.
"""

from __future__ import annotations

from agent.answerer import Answerer, ExtractiveAnswerer, GeminiAnswerer
from agent.grounding.embeddings import Embedder, VoyageEmbedder
from agent.grounding.judge import GeminiJudge, HeuristicJudge, Judge
from agent.grounding.scorer import GroundingScorer
from agent.ledger import Ledger, LedgerStore
from agent.llm import get_gemini_client
from agent.pg_ledger import PgLedger
from registry.pg import psycopg_connect
from shared.chain import ChainReader, JsonRpcClient
from shared.circle_wallets import CircleWalletsClient
from shared.config import Settings
from shared.config import settings as default_settings
from shared.erc8004 import Erc8004Client
from shared.erc8183 import Erc8183Client


def build_circle_wallets(config: Settings | None = None) -> CircleWalletsClient | None:
    """Circle W3S wallets client when ``KERYX_CIRCLE_API_KEY`` is set, else ``None`` (offline)."""
    cfg = config or default_settings
    if not cfg.circle_api_key:
        return None
    return CircleWalletsClient(cfg.circle_api_key, base_url=cfg.circle_api_base)


def build_erc8183(config: Settings | None = None) -> Erc8183Client | None:
    """ERC-8183 job-escrow client when ``KERYX_ERC8183_ENABLED`` is on, else ``None``.

    Reads work with just an RPC url; the job lifecycle writes need ``KERYX_AGENT_PRIVATE_KEY``.
    Disabled by default so nothing touches the network in CI.
    """
    cfg = config or default_settings
    if not cfg.erc8183_enabled or not cfg.rpc_url:
        return None
    rpc = JsonRpcClient(
        cfg.rpc_url, timeout=cfg.chain_rpc_timeout, max_retries=cfg.chain_max_retries
    )
    return Erc8183Client(
        rpc,
        contract=cfg.erc8183_contract,
        usdc_address=cfg.usdc_address,
        chain_id=cfg.arc_chain_id,
        private_key=cfg.agent_private_key or None,
    )


def build_erc8004(config: Settings | None = None) -> Erc8004Client | None:
    """ERC-8004 client when ``KERYX_ERC8004_ENABLED`` is on, else ``None``.

    Reads work with just an RPC url; writes (register/feedback) also need
    ``KERYX_AGENT_PRIVATE_KEY``. Disabled by default so nothing touches the network in CI.
    """
    cfg = config or default_settings
    if not cfg.erc8004_enabled or not cfg.rpc_url:
        return None
    rpc = JsonRpcClient(
        cfg.rpc_url, timeout=cfg.chain_rpc_timeout, max_retries=cfg.chain_max_retries
    )
    return Erc8004Client(
        rpc,
        identity_registry=cfg.erc8004_identity_registry,
        reputation_registry=cfg.erc8004_reputation_registry,
        validation_registry=cfg.erc8004_validation_registry,
        chain_id=cfg.arc_chain_id,
        private_key=cfg.agent_private_key or None,
    )


def build_chain_reader(config: Settings | None = None) -> ChainReader | None:
    """Arc chain reader for ledger verification when ``KERYX_LEDGER_VERIFY_CHAIN`` is on.

    ``None`` (the default) means GET /ledger returns today's mirror with zero RPC reads.
    """
    cfg = config or default_settings
    if not cfg.ledger_verify_chain or not cfg.rpc_url:
        return None
    return ChainReader(
        cfg.rpc_url,
        cfg.usdc_address,
        timeout=cfg.chain_rpc_timeout,
        max_retries=cfg.chain_max_retries,
    )


def build_ledger(config: Settings | None = None) -> LedgerStore:
    """Neon-backed settlement ledger when ``KERYX_DATABASE_URL`` is set, else in-memory.

    Both implement the same ``record``/``metrics``/``recent`` surface; the in-memory ledger
    is the offline default so CI needs no database.
    """
    cfg = config or default_settings
    if cfg.database_url:
        return PgLedger(psycopg_connect(cfg.database_url))
    return Ledger()


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
    gemini = get_gemini_client(cfg)
    if gemini is None:
        return HeuristicJudge()
    return GeminiJudge(
        gemini,
        model=cfg.gemini_judge_model,
        max_tokens=cfg.llm_max_tokens,
        max_retries=cfg.llm_max_retries,
        backoff_base=cfg.llm_backoff_base,
        backoff_cap=cfg.llm_backoff_cap,
    )


def build_answerer(config: Settings | None = None) -> Answerer:
    cfg = config or default_settings
    gemini = get_gemini_client(cfg)
    if gemini is None:
        return ExtractiveAnswerer()
    return GeminiAnswerer(
        gemini,
        model=cfg.gemini_answer_model_resolved,
        max_tokens=cfg.llm_max_tokens,
        max_retries=cfg.llm_max_retries,
        backoff_base=cfg.llm_backoff_base,
        backoff_cap=cfg.llm_backoff_cap,
    )


def build_scorer(
    config: Settings | None = None, *, embedder: Embedder | None = None
) -> GroundingScorer:
    cfg = config or default_settings
    # Share the caller's embedder when given (one instance -> one cache across scoring +
    # retrieval); otherwise derive from config (Voyage if keyed, else BagOfWords default).
    emb = embedder if embedder is not None else build_embedder(cfg)
    return GroundingScorer(config=cfg, embedder=emb, judge=build_judge(cfg))
