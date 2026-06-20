"""A fake psycopg connection/cursor for testing the Pg-backed store + ledger with NO
database and NO driver — the persistence equivalent of httpx.MockTransport.

A ``FakeDB`` records every executed (sql, params) pair and answers reads through a
``responder(sql, params) -> rows`` callable, so tests assert the SQL is parameterized and
the row<->domain mapping is correct without a server.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

Row = tuple[Any, ...]
Responder = Callable[[str, Sequence[Any] | None], list[Row]]


class FakeCursor:
    def __init__(self, db: FakeDB) -> None:
        self._db = db

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, query: str, params: Sequence[Any] | None = None) -> object:
        self._db.calls.append((query, list(params) if params is not None else None))
        self._db.last = self._db.responder(query, params)
        return self

    def fetchone(self) -> Row | None:
        return self._db.last[0] if self._db.last else None

    def fetchall(self) -> list[Row]:
        return list(self._db.last)


class FakeConn:
    def __init__(self, db: FakeDB) -> None:
        self._db = db

    def __enter__(self) -> FakeConn:
        return self

    def __exit__(self, *exc: object) -> None:
        self._db.commits += 1

    def cursor(self) -> FakeCursor:
        self._db.cursors += 1
        return FakeCursor(self._db)


class FakeDB:
    """Shared recording target; ``connect`` is a drop-in ``ConnectFn``."""

    def __init__(self, responder: Responder | None = None) -> None:
        self.calls: list[tuple[str, list[Any] | None]] = []
        self.commits = 0
        self.cursors = 0
        self.last: list[Row] = []
        self.responder: Responder = responder or (lambda _q, _p: [])

    def connect(self) -> FakeConn:
        return FakeConn(self)

    def executed(self) -> list[str]:
        return [q for q, _ in self.calls]

    def params_for(self, sql_substr: str) -> list[Any] | None:
        for q, p in self.calls:
            if sql_substr in q:
                return p
        return None
