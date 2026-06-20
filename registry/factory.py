"""Select the source store from config: Neon-backed when ``KERYX_DATABASE_URL`` is set,
the offline seeded in-memory registry otherwise (CI / zero-config default).

Mirrors the LLM/embedder factory pattern: the real (DB) path activates on config; without
it nothing imports a driver and behavior is exactly today's in-memory store.
"""

from __future__ import annotations

from registry.fixtures import seeded_registry
from registry.pg import psycopg_connect
from registry.pg_store import PgSourceStore
from registry.store import SourceStore
from shared.config import Settings
from shared.config import settings as default_settings


def build_store(config: Settings | None = None) -> SourceStore:
    cfg = config or default_settings
    if cfg.database_url:
        return PgSourceStore(psycopg_connect(cfg.database_url))
    return seeded_registry()
