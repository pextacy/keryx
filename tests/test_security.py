"""API security — opt-in API-key auth on settlement endpoints + per-IP rate limiting."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import agent.main as main
from agent.security import RateLimiter, require_api_key

PAYOUT = {"amount": "0.01", "contributors": [{"wallet": "0x" + "a" * 40, "share": "1"}]}


def _client() -> TestClient:
    return TestClient(main.app)


# --- rate limiter (unit) ----------------------------------------------------


def test_rate_limiter_disabled_allows_everything() -> None:
    rl = RateLimiter(0)
    assert not rl.enabled
    assert all(rl.allow("ip") for _ in range(1000))


def test_rate_limiter_caps_per_window_then_resets() -> None:
    clock = [1000.0]
    rl = RateLimiter(2, now=lambda: clock[0])
    assert rl.allow("ip") and rl.allow("ip")  # 2 allowed
    assert not rl.allow("ip")  # 3rd blocked in the same minute
    clock[0] += 60  # next window
    assert rl.allow("ip")


def test_rate_limiter_is_per_key() -> None:
    rl = RateLimiter(1)
    assert rl.allow("a") and rl.allow("b")  # separate clients
    assert not rl.allow("a")  # a exhausted


# --- api-key auth -----------------------------------------------------------


def test_require_api_key_noop_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shared.config.settings.api_key", "")
    require_api_key(None)  # no key configured -> no exception


def test_settlement_endpoint_requires_key_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shared.config.settings.api_key", "secret")
    c = _client()
    assert c.post("/payout", json=PAYOUT).status_code == 401  # missing
    assert c.post("/payout", json=PAYOUT, headers={"X-API-Key": "wrong"}).status_code == 401
    assert c.post("/payout", json=PAYOUT, headers={"X-API-Key": "secret"}).status_code == 200


def test_reads_stay_open_when_key_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shared.config.settings.api_key", "secret")
    # /ask and GET reads are not money-movers; they remain key-free.
    assert _client().get("/healthz").status_code == 200


# --- rate-limit middleware (integration) ------------------------------------


def test_rate_limit_middleware_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "_rate_limiter", RateLimiter(2))
    c = _client()
    assert c.get("/healthz").status_code == 200
    assert c.get("/healthz").status_code == 200
    assert c.get("/healthz").status_code == 429  # third request in the window is capped
