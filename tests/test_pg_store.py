"""PgSourceStore — row<->Source mapping, parameterized upserts, pgvector ANN. No DB."""

from __future__ import annotations

import json
from typing import Any

from registry.models import Source
from registry.pg import to_vector_literal
from registry.pg_store import PgSourceStore
from tests._pg_fakes import FakeDB, Row

SRC = Source(
    source_id="src_abc",
    url="https://example.com/post",
    title="A Post",
    text="some grounding text",
    author="alice",
    author_wallet="0x" + "a" * 40,
    meta={"pubDate": "2026-01-01"},
)


def _raw(source: Source) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "text": source.text,
        "author": source.author,
        "meta": source.meta,
    }


def test_resolve_wallet_returns_wallet() -> None:
    db = FakeDB(lambda q, p: [("0xdead",)] if "wallet_address" in q else [])
    store = PgSourceStore(db.connect)
    assert store.resolve_wallet("alice") == "0xdead"
    assert db.params_for("wallet_address") == ["alice"]


def test_resolve_wallet_none_when_absent() -> None:
    db = FakeDB(lambda q, p: [])
    assert PgSourceStore(db.connect).resolve_wallet("nobody") is None


def test_add_upserts_author_then_source_parameterized() -> None:
    db = FakeDB(lambda q, p: [(7,)] if "RETURNING id" in q else [])
    PgSourceStore(db.connect).add(SRC)
    sql = " ".join(db.executed())
    assert "INSERT INTO authors" in sql
    assert "INSERT INTO sources" in sql
    # Author upsert carries (author, wallet, meta-json).
    assert db.params_for("INSERT INTO authors")[:2] == ["alice", "0x" + "a" * 40]
    # Source upsert links the returned author id and stores NULL embedding by default.
    src_params = db.params_for("INSERT INTO sources")
    assert src_params is not None
    assert src_params[0] == SRC.url and src_params[2] == 7 and src_params[-1] is None
    # The literal wallet/url never appears interpolated in the SQL text (injection-safe).
    assert SRC.url not in sql and SRC.author_wallet not in sql


def test_add_with_embedding_sends_vector_literal() -> None:
    db = FakeDB(lambda q, p: [(7,)] if "RETURNING id" in q else [])
    store = PgSourceStore(db.connect)
    store.add_with_embedding(SRC, [0.1, 0.2, 0.3])
    src_params = db.params_for("INSERT INTO sources")
    assert src_params is not None
    assert src_params[-1] == to_vector_literal([0.1, 0.2, 0.3]) == "[0.1,0.2,0.3]"


def test_add_without_wallet_resolves_existing_author_id() -> None:
    no_wallet = Source(source_id="s2", url="u2", title="t2", text="x", author="bob")
    db = FakeDB(lambda q, p: [(99,)] if q.strip().startswith("SELECT id FROM authors") else [])
    PgSourceStore(db.connect).add(no_wallet)
    # No author upsert (no wallet); links the existing author id 99.
    assert "INSERT INTO authors" not in " ".join(db.executed())
    assert db.params_for("INSERT INTO sources")[2] == 99


def _source_row(source: Source, wallet: str | None, *, as_text: bool = False) -> Row:
    raw: Any = json.dumps(_raw(source)) if as_text else _raw(source)
    return (source.url, source.title, raw, wallet)


def test_all_maps_rows_to_sources() -> None:
    db = FakeDB(lambda q, p: [_source_row(SRC, "0xfeed")] if "FROM sources s" in q else [])
    got = PgSourceStore(db.connect).all()
    assert len(got) == 1
    s = got[0]
    assert s.source_id == "src_abc" and s.text == "some grounding text"
    assert s.author == "alice" and s.author_wallet == "0xfeed" and s.payable


def test_all_handles_json_text_raw_dataitem() -> None:
    db = FakeDB(lambda q, p: [_source_row(SRC, None, as_text=True)] if "FROM sources" in q else [])
    s = PgSourceStore(db.connect).all()[0]
    assert s.source_id == "src_abc" and s.author_wallet is None and not s.payable


def test_get_filters_by_source_id() -> None:
    db = FakeDB(lambda q, p: [_source_row(SRC, "0x1")] if "source_id" in q else [])
    s = PgSourceStore(db.connect).get("src_abc")
    assert s is not None and s.source_id == "src_abc"
    assert db.params_for("source_id") == ["src_abc"]


def test_get_returns_none_when_missing() -> None:
    assert PgSourceStore(FakeDB().connect).get("nope") is None


def test_nearest_builds_ann_query_with_vector_and_k() -> None:
    db = FakeDB(lambda q, p: [_source_row(SRC, "0x1")] if "<=>" in q else [])
    out = PgSourceStore(db.connect).nearest([1.0, 0.0], k=3)
    assert len(out) == 1
    params = db.params_for("<=>")
    assert params is not None
    assert params[0] == "[1.0,0.0]" and params[1] == 3
