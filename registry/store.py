"""Source/registry store — in-memory by default, Neon-backed later.

Phase 2 runs entirely in-memory so /ask works with zero infra. The Neon-backed store
(authors/sources tables) lands when DATABASE_URL is wired; it mirrors this interface.
Chain stays canonical for payments — this is only the registry + source cache.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from registry.models import Source


@runtime_checkable
class SourceStore(Protocol):
    def add(self, source: Source) -> None: ...
    def all(self) -> list[Source]: ...
    def resolve_wallet(self, author: str) -> str | None: ...


class InMemoryRegistry:
    """Author->wallet map + source cache held in memory."""

    def __init__(self, wallets: dict[str, str] | None = None) -> None:
        self._wallets: dict[str, str] = dict(wallets or {})
        self._sources: dict[str, Source] = {}

    def register_author(self, author: str, wallet: str) -> None:
        self._wallets[author] = wallet

    def resolve_wallet(self, author: str) -> str | None:
        return self._wallets.get(author)

    def add(self, source: Source) -> None:
        self._sources[source.source_id] = source

    def add_many(self, sources: Iterable[Source]) -> None:
        for s in sources:
            self.add(s)

    def all(self) -> list[Source]:
        return list(self._sources.values())

    def get(self, source_id: str) -> Source | None:
        return self._sources.get(source_id)
