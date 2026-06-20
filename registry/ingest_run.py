"""Runnable RSSHub ingest — fetch the configured routes into the active store.

    python -m registry.ingest_run

Writes Sources into the Neon-backed store when KERYX_DATABASE_URL is set, else the
in-memory seeded registry (a no-op unless KERYX_RSSHUB_ROUTES is configured). Safe to run
repeatedly: sources upsert by canonical URL.
"""

from __future__ import annotations

from registry.factory import build_store
from registry.ingest import populate_store


def main() -> int:
    store = build_store()
    added = populate_store(store)
    print(f"RSSHub ingest: added {added} source(s) into {type(store).__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
