"""registry/ (CC-B leads): author->wallet map + RSSHub ingest.

Reads RSSHub DataItem.link (canonical URL) + DataItem.author into the authors
(author->wallet) registry and sources cache.
"""

from __future__ import annotations

from registry.fixtures import seeded_registry
from registry.ingest import RsshubIngestor, parse_dataitem, parse_dataitems, populate_store
from registry.models import Source
from registry.store import InMemoryRegistry, SourceStore

__all__ = [
    "InMemoryRegistry",
    "RsshubIngestor",
    "Source",
    "SourceStore",
    "parse_dataitem",
    "parse_dataitems",
    "populate_store",
    "seeded_registry",
]
