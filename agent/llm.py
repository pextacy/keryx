"""LLM client wiring — shared by the grounding judge and the answerer.

The moat (grounding) and answer synthesis run on Gemini when an API key is present
(``KERYX_GEMINI_API_KEY``) and fall back to the offline heuristics otherwise, so CI and
zero-config demos stay deterministic and dependency-free. Centralizing the client here
keeps the model defaults in one place.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

import httpx

from shared.config import Settings
from shared.config import settings as default_settings

if TYPE_CHECKING:
    from google.genai import Client as GeminiClient

T = TypeVar("T")

# Transient HTTP statuses worth retrying: rate-limit (429) + the 5xx family. Everything
# else (401/403/400/404 …) is permanent and should degrade to the offline path at once.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def _is_transient(exc: Exception) -> bool:
    """A transient LLM error: a rate-limit/5xx API error, or a connection/timeout blip."""
    if isinstance(exc, httpx.TimeoutException | httpx.TransportError):
        return True
    code = getattr(exc, "code", None)  # google.genai APIError carries the HTTP status here
    return isinstance(code, int) and code in _RETRYABLE_STATUS


def call_with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int,
    backoff_base: float,
    backoff_cap: float,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``fn``; retry transient LLM errors (429/5xx, connection/timeout) with bounded
    exponential backoff. Permanent errors (4xx, bugs) propagate immediately so the caller
    can degrade to its offline fallback without burning time on doomed retries.
    """
    last: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — re-raised below; classified by _is_transient
            if not _is_transient(exc) or attempt >= max_retries:
                raise
            last = exc
            sleep(min(backoff_base * (2**attempt), backoff_cap))
    assert last is not None  # unreachable: the loop always returns or raises
    raise last


def llm_enabled(config: Settings | None = None) -> bool:
    """True when a Gemini API key is configured (the real LLM path is active)."""
    return bool((config or default_settings).gemini_api_key)


def get_gemini_client(config: Settings | None = None) -> GeminiClient | None:
    """Construct a Gemini client from settings, or ``None`` if no key is set.

    Returns ``None`` rather than raising so callers can transparently fall back to
    the offline heuristic implementations.
    """
    cfg = config or default_settings
    if not cfg.gemini_api_key:
        return None
    from google.genai import Client

    return Client(api_key=cfg.gemini_api_key)
