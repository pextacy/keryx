"""Neon-backed SourceStore — author->wallet registry + source cache, behind the same
``SourceStore`` interface as ``InMemoryRegistry`` (registry/store.py).

Active only when ``KERYX_DATABASE_URL`` is set; the offline default stays in-memory so CI
and zero-config demos need no database. The in-memory ``Source`` model is richer than the
SQL columns, so the derived fields (source_id, text, author, meta) live in
``sources.raw_dataitem`` (JSONB) while url/title/content_hash/embedding are columns.

All SQL is parameterized (no value interpolation). Chain stays canonical — this is a
registry + cache, never the source of truth for payments.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence

from registry.models import Source
from registry.pg import ConnectFn, Row, to_vector_literal

# --- SQL (parameterized; %s placeholders only) ------------------------------

_UPSERT_AUTHOR = """
INSERT INTO authors (author_url, wallet_address, meta)
VALUES (%s, %s, %s::jsonb)
ON CONFLICT (author_url) DO UPDATE SET wallet_address = EXCLUDED.wallet_address
RETURNING id
"""

_AUTHOR_ID = "SELECT id FROM authors WHERE author_url = %s"

_RESOLVE_WALLET = "SELECT wallet_address FROM authors WHERE author_url = %s"

_UPSERT_SOURCE = """
INSERT INTO sources (url, title, author_ref, content_hash, raw_dataitem, embedding)
VALUES (%s, %s, %s, %s, %s::jsonb, %s::vector)
ON CONFLICT (url) DO UPDATE SET
    title        = EXCLUDED.title,
    author_ref   = EXCLUDED.author_ref,
    content_hash = EXCLUDED.content_hash,
    raw_dataitem = EXCLUDED.raw_dataitem,
    embedding    = COALESCE(EXCLUDED.embedding, sources.embedding)
"""

_SELECT_COLS = """
SELECT s.url, s.title, s.raw_dataitem, a.wallet_address
FROM sources s
LEFT JOIN authors a ON s.author_ref = a.id
"""

_SELECT_ALL = _SELECT_COLS
_SELECT_BY_ID = _SELECT_COLS + "WHERE s.raw_dataitem->>'source_id' = %s"
_NEAREST = _SELECT_COLS + (
    "WHERE s.embedding IS NOT NULL ORDER BY s.embedding <=> %s::vector LIMIT %s"
)


def _content_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()


def _row_to_source(row: Row) -> Source:
    """Reconstruct a Source from (url, title, raw_dataitem, wallet_address)."""
    url, title, raw, wallet = row
    raw = raw or {}
    if isinstance(raw, str):  # some drivers hand back JSON text
        raw = json.loads(raw)
    meta = raw.get("meta") or {}
    return Source(
        source_id=raw.get("source_id") or url,
        url=url,
        title=title or url,
        text=raw.get("text") or "",
        author=raw.get("author") or "unknown",
        author_wallet=wallet,
        meta={str(k): str(v) for k, v in meta.items()},
    )


class PgSourceStore:
    """Postgres implementation of ``SourceStore`` (+ the InMemoryRegistry helpers)."""

    def __init__(self, connect: ConnectFn) -> None:
        self._connect = connect

    # --- registry (author -> wallet) ----------------------------------------

    def register_author(self, author: str, wallet: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(_UPSERT_AUTHOR, [author, wallet, "{}"])

    def resolve_wallet(self, author: str) -> str | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(_RESOLVE_WALLET, [author])
            row = cur.fetchone()
        return None if row is None else (None if row[0] is None else str(row[0]))

    # --- source cache --------------------------------------------------------

    def add(self, source: Source) -> None:
        self._add(source, None)

    def add_with_embedding(self, source: Source, embedding: Sequence[float] | None) -> None:
        """Upsert a source together with its dense embedding (pgvector)."""
        self._add(source, embedding)

    def _add(self, source: Source, embedding: Sequence[float] | None) -> None:
        author_ref = self._upsert_author(source)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                _UPSERT_SOURCE,
                [
                    source.url,
                    source.title,
                    author_ref,
                    _content_hash(source.text),
                    json.dumps(
                        {
                            "source_id": source.source_id,
                            "text": source.text,
                            "author": source.author,
                            "meta": source.meta,
                        }
                    ),
                    to_vector_literal(embedding),
                ],
            )

    def _upsert_author(self, source: Source) -> int | None:
        if not source.author_wallet:
            # Still resolve an existing author row so the source can link to it.
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(_AUTHOR_ID, [source.author])
                row = cur.fetchone()
            return None if row is None else int(row[0])
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(_UPSERT_AUTHOR, [source.author, source.author_wallet, "{}"])
            row = cur.fetchone()
        return None if row is None else int(row[0])

    def add_many(self, sources: Iterable[Source]) -> None:
        for s in sources:
            self.add(s)

    def all(self) -> list[Source]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(_SELECT_ALL)
            rows = cur.fetchall()
        return [_row_to_source(r) for r in rows]

    def get(self, source_id: str) -> Source | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(_SELECT_BY_ID, [source_id])
            row = cur.fetchone()
        return None if row is None else _row_to_source(row)

    def nearest(self, embedding: Sequence[float], k: int = 5) -> list[Source]:
        """pgvector cosine nearest sources to a query embedding (ANN)."""
        literal = to_vector_literal(embedding)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(_NEAREST, [literal, k])
            rows = cur.fetchall()
        return [_row_to_source(r) for r in rows]
