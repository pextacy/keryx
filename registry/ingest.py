"""RSSHub ingest — DataItem.link + DataItem.author -> sources + author->wallet.

docs.md: read RSSHub items into the source cache + registry. We parse the canonical
DataItem shape; live fetch via httpx is optional so CI/offline runs use the seeded corpus
instead. HTML in descriptions is stripped to plain text for grounding.

Production path: ``RsshubIngestor`` (pooled client, explicit timeout, bounded retry) and
``populate_store`` fetch a configured route set and write Sources into the active store —
degrading to the seeded corpus on any failure so the agent is never left without sources.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections.abc import Callable, Iterable
from typing import Any

import httpx

from registry.models import Source
from registry.store import SourceStore
from shared.config import settings

log = logging.getLogger("keryx.registry.ingest")

_TAG = re.compile(r"<[^>]+>")
WalletResolver = Callable[[str], str | None]

# Transient HTTP statuses worth retrying; everything else is permanent.
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", text or "")).strip()


def _source_id(link: str) -> str:
    return "src_" + hashlib.sha256(link.encode()).hexdigest()[:16]


def parse_dataitem(item: dict[str, Any], resolve_wallet: WalletResolver) -> Source | None:
    """Map one RSSHub DataItem to a Source. Returns None if it has no canonical link."""
    link = (item.get("link") or "").strip()
    if not link:
        return None
    author = (item.get("author") or "").strip() or "unknown"
    text = _strip_html(item.get("description") or item.get("content") or item.get("title") or "")
    return Source(
        source_id=_source_id(link),
        url=link,
        title=(item.get("title") or link).strip(),
        text=text,
        author=author,
        author_wallet=resolve_wallet(author),
        meta={"pubDate": str(item.get("pubDate", ""))},
    )


def parse_dataitems(
    items: Iterable[dict[str, Any]], resolve_wallet: WalletResolver
) -> list[Source]:
    out = [parse_dataitem(i, resolve_wallet) for i in items]
    return [s for s in out if s is not None]


class RsshubIngestor:
    """Hardened RSSHub fetch: one pooled client, explicit timeout, bounded retry.

    RSSHub serves JSON at ``<base>/<route>?format=json`` with an ``items`` array. A failed
    route is logged and skipped (the others still ingest); cross-route results are deduped by
    canonical URL. ``close()`` releases the owned client (never an injected one).
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = (base_url or settings.rsshub_base_url).rstrip("/")
        self.max_retries = settings.rsshub_max_retries if max_retries is None else max_retries
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(settings.rsshub_timeout if timeout is None else timeout),
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )
        self._sleep: Callable[[float], None] = time.sleep  # injectable in tests

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            try:
                self._client.close()
            except Exception as exc:  # noqa: BLE001 — close must never raise
                log.warning("RsshubIngestor client close failed: %s", exc)
            self._owns_client = False

    def _get_items(self, route: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/{route.lstrip('/')}"
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._client.get(url, params={"format": "json"})
                resp.raise_for_status()
                body = resp.json()
                items = body.get("items", []) if isinstance(body, dict) else []
                return [i for i in items if isinstance(i, dict)]
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in _RETRYABLE_STATUS:
                    raise
                last_exc = exc
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
            if attempt < self.max_retries:
                self._sleep(min(0.2 * (2**attempt), 2.0))
        assert last_exc is not None
        raise last_exc

    def fetch(self, route: str, resolve_wallet: WalletResolver) -> list[Source]:
        return parse_dataitems(self._get_items(route), resolve_wallet)

    def ingest(self, routes: Iterable[str], resolve_wallet: WalletResolver) -> list[Source]:
        seen: set[str] = set()
        out: list[Source] = []
        for route in routes:
            try:
                sources = self.fetch(route, resolve_wallet)
            except Exception as exc:  # noqa: BLE001 — one bad route never sinks the rest
                log.warning("RSSHub route %r failed, skipping: %s", route, exc)
                continue
            for s in sources:
                if s.url in seen:
                    continue
                seen.add(s.url)
                out.append(s)
        return out


def _configured_routes() -> list[str]:
    return [r.strip() for r in settings.rsshub_routes.split(",") if r.strip()]


def populate_store(
    store: SourceStore,
    *,
    routes: Iterable[str] | None = None,
    ingestor: RsshubIngestor | None = None,
) -> int:
    """Fetch the configured RSSHub routes into ``store``; return the count added.

    Offline default (no routes configured) is a no-op: the store keeps its seeded corpus.
    On any fetch failure we degrade — the store is left as-is (seeded), never emptied — so
    the agent always has sources. Author->wallet resolution uses the store's registry.
    """
    route_list = list(routes) if routes is not None else _configured_routes()
    if not route_list:
        return 0
    ing = ingestor or RsshubIngestor()
    try:
        sources = ing.ingest(route_list, store.resolve_wallet)
    except Exception as exc:  # noqa: BLE001 — degrade to the seeded corpus
        log.warning("RSSHub ingest failed, keeping seeded corpus: %s", exc)
        return 0
    finally:
        if ingestor is None:
            ing.close()
    for s in sources:
        store.add(s)
    return len(sources)
