"""Verify Neon is reachable and the schema/extension are present.

Satisfies the Phase 0 DoD item "Neon reachable with pgvector". Requires
KERYX_DATABASE_URL in the environment / .env.

Run: python scripts/db_check.py
"""

from __future__ import annotations

import sys

from shared.config import settings


def main() -> int:
    if not settings.database_url:
        print("KERYX_DATABASE_URL not set — add your Neon connection string to .env")
        return 2
    try:
        import psycopg
    except ImportError:
        print("psycopg not installed — run: pip install -e '.[dev]'")
        return 2

    try:
        with (
            psycopg.connect(settings.database_url, connect_timeout=10) as conn,
            conn.cursor() as cur,
        ):
            cur.execute("SELECT 1")
            cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            has_vector = cur.fetchone() is not None
            cur.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
            tables = {r[0] for r in cur.fetchall()}
    except Exception as exc:  # noqa: BLE001 - report any connection failure plainly
        print(f"Neon connection FAILED: {exc}")
        return 1

    expected = {"authors", "sources", "sessions", "citations_index"}
    print("Neon reachable: OK")
    print(f"pgvector extension: {'OK' if has_vector else 'MISSING — run migration 0001'}")
    missing = expected - tables
    print(f"schema tables: {'OK' if not missing else f'MISSING {sorted(missing)}'}")
    return 0 if has_vector and not missing else 1


if __name__ == "__main__":
    sys.exit(main())
