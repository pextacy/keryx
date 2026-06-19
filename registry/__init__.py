"""registry/ (CC-B leads): author->wallet map + RSSHub ingest.

Reads RSSHub DataItem.link (canonical URL) + DataItem.author into the authors
(author->wallet) registry and sources cache.
"""

from __future__ import annotations

from registry.fixtures import seeded_registry
from registry.ingest import fetch_route, parse_dataitem, parse_dataitems
from registry.models import Source
from registry.store import InMemoryRegistry, SourceStore

__all__ = [
    "InMemoryRegistry",
    "Source",
    "SourceStore",
    "fetch_route",
    "parse_dataitem",
    "parse_dataitems",
    "seeded_registry",
]
