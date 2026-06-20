"""Postgres plumbing for the Neon-backed store + ledger.

The off-chain store is a fast read-index / registry / cache only — chain stays canonical
(AGENTS.md #4). Connections are short-lived and created per operation (Neon pools
server-side), which keeps the dashboard read path simple and free of stale-connection
bugs. A ``ConnectFn`` is injectable so unit tests run against a fake connection with NO
database and NO driver import (see tests/_pg_fakes.py); the offline default never builds
one at all.

Typed structurally via ``Connection``/``Cursor`` Protocols so mypy --strict passes without
importing psycopg at type-check time; the real psycopg objects satisfy them at runtime.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Protocol, cast, runtime_checkable

# A bound SQL parameter (we only ever pass scalars / json-strings / vector-literals).
Param = Any
Row = tuple[Any, ...]


@runtime_checkable
class Cursor(Protocol):
    def __enter__(self) -> Cursor: ...
    def __exit__(self, *exc: object) -> None: ...
    def execute(self, query: str, params: Sequence[Param] | None = ...) -> object: ...
    def fetchone(self) -> Row | None: ...
    def fetchall(self) -> list[Row]: ...


@runtime_checkable
class Connection(Protocol):
    def __enter__(self) -> Connection: ...
    def __exit__(self, *exc: object) -> None: ...
    def cursor(self) -> Cursor: ...


# Opens a connection usable as a context manager (`with connect() as conn:`), committing
# and closing on exit. Injectable for tests.
ConnectFn = Callable[[], Connection]


def psycopg_connect(dsn: str) -> ConnectFn:
    """A ``ConnectFn`` that opens a real psycopg connection to ``dsn`` (imported lazily)."""

    def _connect() -> Connection:
        import psycopg  # lazy: only the Pg path needs the driver

        return cast(Connection, psycopg.connect(dsn))

    return _connect


def to_vector_literal(vec: Sequence[float] | None) -> str | None:
    """Format a dense vector as a pgvector text literal (``[1,2,3]``), or ``None``.

    pgvector accepts ``'[...]'::vector``; ``None`` maps to SQL ``NULL`` so a source with no
    embedding is stored without one.
    """
    if vec is None:
        return None
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"
