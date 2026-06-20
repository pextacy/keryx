"""API security — opt-in API-key auth for settlement endpoints + per-IP rate limiting.

The money-moving endpoints (/payout, /bond, /stream, /royalties, /qf, /reputation) should not
be wide open. Both controls are OFF by default so the public /ask demo and CI stay open and
deterministic, and activate from config:
  - KERYX_API_KEY set        -> writes require a matching ``X-API-Key`` header (else 401).
  - KERYX_RATE_LIMIT_PER_MINUTE > 0 -> per-IP fixed-window cap across all endpoints (else 429).

In-memory and dependency-free (no slowapi); production behind a single instance. Behind a
load balancer, trust the proxy's client-IP header.
"""

from __future__ import annotations

import hmac
import threading
import time
from collections.abc import Callable

from fastapi import Header, HTTPException

from shared.config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency: enforce ``X-API-Key`` when ``KERYX_API_KEY`` is configured.

    No-op when no key is set (open demo default). Uses a constant-time compare.
    """
    expected = settings.api_key
    if not expected:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


class RateLimiter:
    """Per-key fixed-window request limiter. ``per_minute <= 0`` disables it."""

    def __init__(self, per_minute: int, *, now: Callable[[], float] = time.time) -> None:
        self.per_minute = per_minute
        self._now = now
        self._hits: dict[str, tuple[int, int]] = {}  # key -> (window, count)
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.per_minute > 0

    def allow(self, key: str) -> bool:
        """True if ``key`` may make another request in the current minute window."""
        if not self.enabled:
            return True
        window = int(self._now()) // 60
        with self._lock:
            w, count = self._hits.get(key, (window, 0))
            if w != window:
                w, count = window, 0
            count += 1
            self._hits[key] = (w, count)
            return count <= self.per_minute
