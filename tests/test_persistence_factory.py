"""Store/ledger factories: Pg-backed when DATABASE_URL is set, in-memory default otherwise.

The offline default must be byte-for-byte today's behavior (seeded in-memory registry +
in-memory ledger) with no driver/DB involvement — invariant #1.
"""

from __future__ import annotations

import os

import pytest

from agent.factory import build_ledger
from agent.ledger import Ledger
from agent.pg_ledger import PgLedger
from registry.factory import build_store
from registry.pg_store import PgSourceStore
from registry.store import InMemoryRegistry
from shared.config import Settings

_DSN = "postgresql://u:p@localhost/db"


def test_build_store_offline_is_seeded_in_memory() -> None:
    store = build_store(Settings(database_url=""))
    assert isinstance(store, InMemoryRegistry)
    assert len(store.all()) > 0  # seeded corpus present, zero DB calls


def test_build_store_activates_pg_with_dsn() -> None:
    assert isinstance(build_store(Settings(database_url=_DSN)), PgSourceStore)


def test_build_ledger_offline_is_in_memory() -> None:
    assert isinstance(build_ledger(Settings(database_url="")), Ledger)


def test_build_ledger_activates_pg_with_dsn() -> None:
    assert isinstance(build_ledger(Settings(database_url=_DSN)), PgLedger)


def test_pg_factories_do_not_connect_eagerly() -> None:
    # Constructing the Pg-backed components must not open a connection (lazy ConnectFn).
    store = build_store(Settings(database_url=_DSN))
    ledger = build_ledger(Settings(database_url=_DSN))
    assert isinstance(store, PgSourceStore) and isinstance(ledger, PgLedger)


@pytest.mark.skipif(
    not os.environ.get("KERYX_DATABASE_URL"),
    reason="integration: set KERYX_DATABASE_URL (Neon) and apply db/migrations to run",
)
def test_pg_roundtrip_integration() -> None:  # pragma: no cover - needs real Neon
    from registry.models import Source

    store = build_store()
    store.register_author("itest-author", "0x" + "b" * 40)  # type: ignore[union-attr]
    store.add(
        Source(
            source_id="itest-src",
            url="https://integration.test/post",
            title="Integration",
            text="integration grounding text",
            author="itest-author",
            author_wallet="0x" + "b" * 40,
        )
    )
    urls = {s.url for s in store.all()}
    assert "https://integration.test/post" in urls
