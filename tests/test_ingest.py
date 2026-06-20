"""RSSHub ingest — pure DataItem parsing + hardened fetch/dedup/degrade. No network."""

from __future__ import annotations

from typing import Any

import httpx

from registry.ingest import (
    RsshubIngestor,
    parse_dataitem,
    parse_dataitems,
    populate_store,
)
from registry.store import InMemoryRegistry

WALLET = "0x" + "a" * 40


def _resolve(author: str) -> str | None:
    return WALLET if author == "alice" else None


def _item(
    link: str, author: str = "alice", desc: str = "<p>hello <b>world</b></p>"
) -> dict[str, Any]:
    return {
        "link": link,
        "author": author,
        "description": desc,
        "title": "T",
        "pubDate": "2026-01-01",
    }


def _client(routes: dict[str, list[dict[str, Any]]]) -> httpx.Client:
    def _handler(request: httpx.Request) -> httpx.Response:
        items = routes.get(request.url.path, [])
        return httpx.Response(200, json={"items": items})

    return httpx.Client(transport=httpx.MockTransport(_handler))


def _ingestor(handler: Any, **kw: Any) -> RsshubIngestor:
    ing = RsshubIngestor(
        base_url="http://rsshub", client=httpx.Client(transport=httpx.MockTransport(handler)), **kw
    )
    ing._sleep = lambda _s: None
    return ing


# --- pure parsing -----------------------------------------------------------


def test_parse_dataitem_strips_html_and_resolves_wallet() -> None:
    s = parse_dataitem(_item("https://x.com/a"), _resolve)
    assert s is not None
    assert s.text == "hello world" and s.author == "alice" and s.author_wallet == WALLET
    assert s.url == "https://x.com/a"


def test_parse_dataitem_none_without_link() -> None:
    assert parse_dataitem({"author": "alice"}, _resolve) is None


def test_parse_dataitems_drops_linkless() -> None:
    out = parse_dataitems([_item("https://x.com/a"), {"author": "x"}], _resolve)
    assert len(out) == 1


# --- hardened fetch ---------------------------------------------------------


def test_fetch_parses_route() -> None:
    ing = _ingestor(lambda r: httpx.Response(200, json={"items": [_item("https://x.com/a")]}))
    out = ing.fetch("/feed", _resolve)
    assert len(out) == 1 and out[0].url == "https://x.com/a"


def test_fetch_retries_then_succeeds() -> None:
    calls = {"n": 0}

    def _h(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"items": [_item("https://x.com/a")]})

    ing = _ingestor(_h, max_retries=2)
    assert len(ing.fetch("/feed", _resolve)) == 1 and calls["n"] == 3


def test_ingest_dedups_across_routes() -> None:
    routes = {
        "/r1": [_item("https://x.com/a"), _item("https://x.com/b")],
        "/r2": [_item("https://x.com/b"), _item("https://x.com/c")],  # b duplicates r1
    }
    ing = RsshubIngestor(base_url="http://rsshub", client=_client(routes))
    ing._sleep = lambda _s: None
    out = ing.ingest(["/r1", "/r2"], _resolve)
    assert sorted(s.url for s in out) == ["https://x.com/a", "https://x.com/b", "https://x.com/c"]


def test_ingest_skips_failing_route_but_keeps_others() -> None:
    def _h(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bad":
            return httpx.Response(500)
        return httpx.Response(200, json={"items": [_item("https://x.com/a")]})

    ing = _ingestor(_h, max_retries=1)
    out = ing.ingest(["/bad", "/good"], _resolve)
    assert [s.url for s in out] == ["https://x.com/a"]  # bad degraded, good ingested


# --- populate_store ---------------------------------------------------------


def test_populate_store_no_routes_is_noop() -> None:
    store = InMemoryRegistry()
    assert populate_store(store, routes=[]) == 0
    assert store.all() == []


def test_populate_store_adds_fetched_sources() -> None:
    store = InMemoryRegistry({"alice": WALLET})
    ing = RsshubIngestor(
        base_url="http://rsshub", client=_client({"/feed": [_item("https://x.com/a")]})
    )
    ing._sleep = lambda _s: None
    n = populate_store(store, routes=["/feed"], ingestor=ing)
    assert n == 1
    urls = {s.url for s in store.all()}
    assert "https://x.com/a" in urls
    assert store.all()[0].author_wallet == WALLET  # resolved via store registry


def test_populate_store_degrades_on_total_failure() -> None:
    seeded = InMemoryRegistry({"alice": WALLET})
    seeded.add(parse_dataitem(_item("https://seed.com/x"), _resolve))  # type: ignore[arg-type]
    ing = _ingestor(lambda r: httpx.Response(500), max_retries=0)
    # All routes fail -> 0 added, seeded corpus untouched (never emptied).
    assert populate_store(seeded, routes=["/a"], ingestor=ing) == 0
    assert {s.url for s in seeded.all()} == {"https://seed.com/x"}
