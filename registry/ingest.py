"""RSSHub ingest — DataItem.link + DataItem.author -> sources + author->wallet.

docs.md: read RSSHub items into the source cache + registry. We parse the canonical
DataItem shape; live fetch via httpx is optional (``fetch_route``) so CI/offline runs
use fixtures instead. HTML in descriptions is stripped to plain text for grounding.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable
from typing import Any

import httpx

from registry.models import Source
from shared.config import settings

_TAG = re.compile(r"<[^>]+>")
WalletResolver = Callable[[str], str | None]


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


def fetch_route(
    route: str, resolve_wallet: WalletResolver, *, base_url: str | None = None
) -> list[Source]:
    """Fetch a RSSHub route (JSON) and parse it. Network — not used in CI.

    RSSHub serves JSON at ``<base>/<route>?format=json`` with an ``items`` array.
    """
    base = (base_url or settings.rsshub_base_url).rstrip("/")
    url = f"{base}/{route.lstrip('/')}"
    resp = httpx.get(url, params={"format": "json"}, timeout=20)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return parse_dataitems(items, resolve_wallet)
