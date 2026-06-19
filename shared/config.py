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

    # --- Source ingest ---
    rsshub_base_url: str = Field(default="http://localhost:1200")

    # --- LLM (grounding judge) ---
    anthropic_api_key: str = Field(default="")
    judge_model: str = Field(default="claude-opus-4-8")

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
