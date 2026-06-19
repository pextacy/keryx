"""Registry domain models — the author->wallet map and source cache.

A ``Source`` is a citable unit (one RSSHub DataItem): canonical URL + author + text.
``author_wallet`` is resolved from the registry; sources with no wallet can be
retrieved and evaluated but never paid (no payee).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Source:
    source_id: str
    url: str
    title: str
    text: str
    author: str
    author_wallet: str | None = None
    meta: dict[str, str] = field(default_factory=dict)

    @property
    def payable(self) -> bool:
        return bool(self.author_wallet)
