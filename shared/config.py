"""Central config surface — settlement amounts and infra are config, not hardcoded.

Loaded from environment / .env (see .env.example). CLAUDE.md mandates: floor
$0.000001, per-citation toll $0.001-$0.01, grounding threshold T=0.5. None of these
may be hardcoded in business logic — import ``settings`` instead.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="KERYX_", extra="ignore", case_sensitive=False
    )

    # --- Settlement economics (config, not hardcoded) ---
    usdc_floor: Decimal = Field(default=Decimal("0.000001"))
    citation_toll_min: Decimal = Field(default=Decimal("0.001"))
    citation_toll_max: Decimal = Field(default=Decimal("0.01"))
    grounding_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="T — pay only if g >= T"
    )

    # --- Chain / rail (Arc testnet constants verified vs arc-nanopayments + live RPC) ---
    rpc_url: str = Field(
        default="https://rpc.testnet.arc.network", description="$RPC from arc-canteen"
    )
    arc_chain_id: int = Field(default=0x4CEF52, description="Arc testnet chain id (5042002)")
    usdc_address: str = Field(
        default="0x3600000000000000000000000000000000000000",
        description="USDC token contract on Arc testnet (6 decimals)",
    )
    gateway_wallet: str = Field(
        default="0x0077777d7EBA4688BDeF3E311b846F25870A19B9",
        description="Circle Gateway batching contract (x402 verifyingContract)",
    )

    # --- Off-chain store (Neon — index/registry/cache only; chain is canonical) ---
    database_url: str = Field(default="", description="Neon Postgres connection string")

    # --- Chain-backed ledger verification (opt-in; default off = no RPC reads in CI) ---
    ledger_verify_chain: bool = Field(
        default=False, description="Annotate GET /ledger with on-chain verification via RPC"
    )
    chain_rpc_timeout: float = Field(default=8.0, gt=0)
    chain_max_retries: int = Field(default=2, ge=0)

    # --- ERC-8004 agent identity + reputation (Arc Testnet registries) ---
    # Verified addresses from docs.arc.io ERC-8004 quickstart (testnet.arcscan.app).
    erc8004_identity_registry: str = Field(default="0x8004A818BFB912233c491871b3d84c89A494BD9e")
    erc8004_reputation_registry: str = Field(default="0x8004B663056A597Dffe9eCcC1965A193B7388713")
    erc8004_validation_registry: str = Field(default="0x8004Cb1BF31DAf7788923b405b754f57acEB4272")
    agent_metadata_uri: str = Field(
        default="", description="ERC-8004 agent metadata URI (ipfs://...) for register()"
    )
    erc8004_enabled: bool = Field(
        default=False, description="Enable ERC-8004 identity/reputation endpoints (uses RPC)"
    )

    # --- ERC-8183 AgenticCommerce (job escrow on Arc Testnet) ---
    erc8183_enabled: bool = Field(
        default=False, description="Enable ERC-8183 job-escrow endpoints (uses RPC)"
    )
    erc8183_contract: str = Field(
        default="0x0747EEf0706327138c69792bF28Cd525089e4583",
        description="AgenticCommerce reference implementation (docs.arc.io)",
    )

    # --- Circle Developer-Controlled Wallets (W3S) ---
    circle_api_key: str = Field(default="", description="Circle W3S API key (enables wallet ops)")
    circle_api_base: str = Field(default="https://api.circle.com")

    # --- Source ingest (RSSHub) ---
    rsshub_base_url: str = Field(default="http://localhost:1200")
    rsshub_routes: str = Field(
        default="", description="Comma-separated RSSHub routes to ingest (empty = offline seed)"
    )
    rsshub_timeout: float = Field(default=20.0, gt=0)
    rsshub_max_retries: int = Field(default=2, ge=0)

    # --- LLM (grounding judge + answer synthesis) ---
    # Real Claude path activates when anthropic_api_key is set; offline heuristics otherwise.
    anthropic_api_key: str = Field(default="")
    judge_model: str = Field(default="claude-opus-4-8")
    answer_model: str = Field(
        default="", description="Model for answer synthesis; falls back to judge_model"
    )
    judge_effort: str = Field(default="low", description="effort for the grounding judge")
    answer_effort: str = Field(default="medium", description="effort for answer synthesis")
    llm_max_tokens: int = Field(default=4096, ge=256)

    @property
    def answer_model_resolved(self) -> str:
        return self.answer_model or self.judge_model

    # --- Embeddings (grounding similarity signal) ---
    # Dense path activates when voyage_api_key is set; offline BagOfWords TF-cosine otherwise.
    # Voyage is Anthropic's recommended embeddings provider (Anthropic ships no embeddings API).
    voyage_api_key: str = Field(default="")
    embedding_model: str = Field(default="voyage-3.5")
    # Client knobs — all default to inert/offline-safe values (no value forces network use).
    embedding_connect_timeout: float = Field(default=3.0, gt=0)
    embedding_read_timeout: float = Field(default=10.0, gt=0)
    embedding_max_retries: int = Field(default=2, ge=0)
    embedding_backoff_base: float = Field(default=0.2, ge=0)
    embedding_backoff_cap: float = Field(default=2.0, ge=0)
    embedding_batch_size: int = Field(default=128, ge=1, le=128)
    embedding_cache_size: int = Field(default=512, ge=1)
    embedding_max_input_chars: int = Field(default=32000, ge=1)
    embedding_dimensions: int | None = Field(default=None)

    # --- Grounding score weighting (similarity vs judge) ---
    similarity_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    judge_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    scale_amount_by_g: bool = Field(
        default=True, description="If true, amount scales with g within the toll band"
    )

    # --- Agent identity (attestation signing) ---
    agent_private_key: str = Field(
        default="", description="0x hex secp256k1 key the agent signs attestations with"
    )

    @field_validator("citation_toll_max")
    @classmethod
    def _toll_range_ordered(cls, v: Decimal, info: ValidationInfo) -> Decimal:
        lo = info.data.get("citation_toll_min")
        if lo is not None and v < lo:
            raise ValueError("citation_toll_max must be >= citation_toll_min")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Module-level singleton for convenience.
settings = get_settings()
