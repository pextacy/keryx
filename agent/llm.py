"""Anthropic client wiring — shared by the grounding judge and the answerer.

The moat (grounding) and answer synthesis run on Claude when an API key is present
(``KERYX_ANTHROPIC_API_KEY``) and fall back to the offline heuristics otherwise, so
CI and zero-config demos stay deterministic and dependency-free. Centralizing the
client here keeps model/effort/thinking defaults in one place.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.config import Settings
from shared.config import settings as default_settings

if TYPE_CHECKING:
    from anthropic import Anthropic


def llm_enabled(config: Settings | None = None) -> bool:
    """True when an Anthropic API key is configured (real LLM path is active)."""
    return bool((config or default_settings).anthropic_api_key)


def get_client(config: Settings | None = None) -> Anthropic | None:
    """Construct an Anthropic client from settings, or ``None`` if no key is set.

    Returns ``None`` rather than raising so callers can transparently fall back to
    the offline heuristic implementations.
    """
    cfg = config or default_settings
    if not cfg.anthropic_api_key:
        return None
    from anthropic import Anthropic

    return Anthropic(api_key=cfg.anthropic_api_key)
