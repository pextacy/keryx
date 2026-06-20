"""Similarity signal for grounding — semantic overlap between answer and source.

In production this is dense cosine over real Voyage embeddings (docs.md). For a runnable,
offline, deterministic v1 we ship a bag-of-words TF cosine behind an ``Embedder``
protocol, so the real embedder drops in later without touching the scorer.
"""

from __future__ import annotations

import logging
import math
import re
import threading
import time
from collections import Counter, OrderedDict
from typing import Any, Protocol, runtime_checkable

import httpx

log = logging.getLogger("keryx.grounding.embeddings")

_WORD = re.compile(r"[a-z0-9]+")

# Retryable transport/server statuses (transient); everything else (4xx) is permanent.
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


def _tokenize(text: str) -> list[str]:
    return _WORD.findall(text.lower())


@runtime_checkable
class Embedder(Protocol):
    """Maps text to a sparse vector (key -> weight).

    Lexical embedders key by token; dense embedders key by vector index (``"0"``, ``"1"``…)
    so ``cosine``/``similarity``/the scorer/retrieval stay identical in signature. The
    ``embed_pair`` and ``embed_many`` methods are ADDITIVE batch entry points with default
    loop implementations — they never change the single-text ``embed`` signature.
    """

    def embed(self, text: str) -> dict[str, float]: ...

    def embed_pair(self, a: str, b: str) -> tuple[dict[str, float], dict[str, float]]:
        """Embed two texts so both vectors live in the SAME space (default: two embeds)."""
        return self.embed(a), self.embed(b)

    def embed_many(self, texts: list[str]) -> list[dict[str, float]]:
        """Embed many texts (default: loop). Dense embedders override to batch one POST."""
        return [self.embed(t) for t in texts]


class BagOfWordsEmbedder:
    """Deterministic, offline TF embedder. Good enough for the similarity signal v1."""

    def embed(self, text: str) -> dict[str, float]:
        counts = Counter(_tokenize(text))
        total = sum(counts.values()) or 1
        return {tok: n / total for tok, n in counts.items()}

    def embed_pair(self, a: str, b: str) -> tuple[dict[str, float], dict[str, float]]:
        return self.embed(a), self.embed(b)

    def embed_many(self, texts: list[str]) -> list[dict[str, float]]:
        return [self.embed(t) for t in texts]


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity of two sparse vectors, clamped to [0, 1].

    For non-negative lexical weights the raw cosine is already in [0, 1]. For SIGNED dense
    vectors the clamp also applies: anti-correlated vectors (true cosine < 0) are treated as
    0 grounding — a deliberate decision, you do not pay negative tolls — rather than a
    negative score. Disjoint keys (e.g. a dense vs a lexical vector) yield 0.
    """
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in shared)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def similarity(answer: str, source_text: str, embedder: Embedder | None = None) -> float:
    """Similarity signal in [0,1] between the answer and a candidate source.

    Embeds both texts through ``embed_pair`` so they always share one embedding space — a
    mid-pair degrade re-embeds the first text through the fallback rather than mixing a
    dense and a lexical vector (which would silently zero the cosine).
    """
    emb = embedder or BagOfWordsEmbedder()
    va, vb = emb.embed_pair(answer, source_text)
    return cosine(va, vb)


# --- Dense embeddings (production) ------------------------------------------

_VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
_MAX_CONNECTIONS = 8
_MAX_KEEPALIVE = 4


class VoyageEmbedder:
    """Dense-embedding similarity via Voyage AI — the production swap for BagOfWords.

    Voyage is Anthropic's recommended embeddings provider (Anthropic ships no embeddings
    endpoint). A dense semantic vector replaces the lexical TF vector, so the similarity
    signal captures meaning rather than word overlap. The dense vector is exposed through
    the same sparse ``Embedder`` interface — index-keyed (``{"0": v0, "1": v1, ...}``) —
    so ``cosine``/``similarity``/the scorer/retrieval are all unchanged.

    Networking: a single long-lived pooled ``httpx.Client`` (explicit ``Timeout``/``Limits``)
    is owned for the instance lifetime and reused across every request; ``close()`` releases
    it (idempotent, never closes an injected test client). Call it from the app's shutdown
    hook.

    Resilience: each request is retried (bounded, hand-rolled backoff honoring ``Retry-After``)
    on transient errors before any degrade; a permanent 4xx degrades immediately. Once
    exhausted, the *whole* embedder degrades to the offline ``BagOfWords`` for the rest of its
    life and drops the dense cache, so a query never mixes a dense and a lexical vector.

    Thread-safety: the process-global instance (``agent/main.py``) runs under FastAPI's
    sync-endpoint threadpool. A lock guards only the tiny critical sections (degrade snapshot,
    cache read/write, degrade+clear) — the HTTP request stays OUTSIDE the lock. Once
    ``_degraded`` is observed true under the lock, no cached dense vector is ever returned.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "voyage-3.5",
        connect_timeout: float = 3.0,
        read_timeout: float = 10.0,
        max_retries: int = 2,
        backoff_base: float = 0.2,
        backoff_cap: float = 2.0,
        batch_size: int = 128,
        cache_size: int = 512,
        max_input_chars: int = 32000,
        dimensions: int | None = None,
        fallback: Embedder | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self.batch_size = batch_size
        self.cache_size = cache_size
        self.max_input_chars = max_input_chars
        self.dimensions = dimensions
        self._fallback: Embedder = fallback or BagOfWordsEmbedder()
        # Injected client is owned by the caller (tests); never closed here. Otherwise build
        # ONE pooled client and own it for the instance lifetime.
        self._owns_client = client is None
        self._client: httpx.Client = client or self._build_client()
        self._cache: OrderedDict[str, dict[str, float]] = OrderedDict()
        self._degraded = False
        self._dim: int | None = None
        self._lock = threading.Lock()
        self._sleep = time.sleep  # injectable so tests run without real delays

        # --- observability counters ---
        self.embed_calls = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.api_calls = 0
        self.retries = 0
        self.degrades = 0
        self.batch_count = 0
        self.last_latency_ms = 0.0
        self.total_latency_ms = 0.0

    def _build_client(self) -> httpx.Client:
        timeout = httpx.Timeout(
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=self.read_timeout,
            pool=self.connect_timeout,
        )
        limits = httpx.Limits(
            max_connections=_MAX_CONNECTIONS, max_keepalive_connections=_MAX_KEEPALIVE
        )
        return httpx.Client(timeout=timeout, limits=limits)

    def close(self) -> None:
        """Close the owned pooled client. Idempotent; never closes an injected client."""
        if self._owns_client and self._client is not None:
            try:
                self._client.close()
            except Exception as exc:  # noqa: BLE001 — close must never raise
                log.warning("VoyageEmbedder client close failed: %s", exc)
            self._owns_client = False

    # --- HTTP + parsing ------------------------------------------------------

    def _post(self, inputs: list[str]) -> Any:
        payload: dict[str, Any] = {"input": inputs, "model": self.model}
        if self.dimensions is not None:
            payload["output_dimension"] = self.dimensions
            payload["truncation"] = True
        headers = {"Authorization": f"Bearer {self._api_key}"}
        start = time.perf_counter()
        try:
            resp = self._client.post(_VOYAGE_URL, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
        finally:
            elapsed = (time.perf_counter() - start) * 1000.0
            self.last_latency_ms = elapsed
            self.total_latency_ms += elapsed
            self.api_calls += 1

    def _parse_vectors(self, body: Any, expected: int) -> list[list[float]]:
        if not isinstance(body, dict) or "data" not in body:
            raise ValueError("Voyage response missing 'data'")
        data = body["data"]
        if not isinstance(data, list) or len(data) != expected:
            raise ValueError("Voyage response 'data' length mismatch")
        vectors: list[list[float]] = []
        for item in data:
            if not isinstance(item, dict) or "embedding" not in item:
                raise ValueError("Voyage response missing 'embedding'")
            raw = item["embedding"]
            if not isinstance(raw, list) or not raw:
                raise ValueError("empty or non-list embedding in Voyage response")
            vec = [float(x) for x in raw]
            if any(math.isnan(v) or math.isinf(v) for v in vec):
                raise ValueError("non-finite value in Voyage embedding")
            self._check_dim(len(vec))
            vectors.append(vec)
        return vectors

    def _check_dim(self, dim: int) -> None:
        if self._dim is None:
            self._dim = dim
        elif dim != self._dim:
            raise ValueError(f"embedding dimension changed: {self._dim} -> {dim}")

    def _request(self, texts: list[str]) -> list[list[float]]:
        body = self._post(texts)
        return self._parse_vectors(body, len(texts))

    def _request_with_retry(self, texts: list[str]) -> list[list[float]]:
        """Bounded retry on transient errors; permanent 4xx propagate immediately."""
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return self._request(texts)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status not in _RETRYABLE_STATUS:
                    raise  # permanent (401/403/400/…) — degrade immediately
                last_exc = exc
                retry_after = _parse_retry_after(exc.response)
                self._backoff(attempt, retry_after)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                self._backoff(attempt, None)
        assert last_exc is not None
        raise last_exc

    def _backoff(self, attempt: int, retry_after: float | None) -> None:
        if attempt >= self.max_retries:
            return  # last attempt failed; do not sleep before propagating
        self.retries += 1
        base = self.backoff_base * (2**attempt)
        # Deterministic-but-jittered: a small attempt-derived fraction, no RNG.
        delay = base + (self.backoff_base * 0.1 * (attempt % 3))
        if retry_after is not None:
            delay = max(delay, retry_after)
        self._sleep(min(delay, self.backoff_cap))

    # --- public API ----------------------------------------------------------

    def embed(self, text: str) -> dict[str, float]:
        self.embed_calls += 1
        key = text.strip()
        # Snapshot degrade + read cache under the lock.
        with self._lock:
            if self._degraded or not key:
                return self._fallback.embed(text)
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                self.cache_hits += 1
                return cached
        self.cache_misses += 1
        try:
            vec = self._request_with_retry([key])[0]
        except Exception as exc:  # noqa: BLE001 — any failure degrades to offline embedder
            self._degrade(exc)
            return self._fallback.embed(text)
        emb = {str(i): v for i, v in enumerate(vec)}
        with self._lock:
            if self._degraded:  # a concurrent failure won — do not leak a dense vector
                return self._fallback.embed(text)
            self._cache_put(key, emb)
        return emb

    def embed_pair(self, a: str, b: str) -> tuple[dict[str, float], dict[str, float]]:
        """Embed two texts in one space; a mid-pair degrade re-embeds ``a`` lexically."""
        va = self.embed(a)
        was_degraded = self.is_degraded
        vb = self.embed(b)
        if self.is_degraded and not was_degraded:
            # The degrade happened while embedding b — va is a stale dense vector. Re-embed a
            # through the fallback so BOTH vectors come from the lexical space.
            return self._fallback.embed(a), vb
        return va, vb

    def embed_many(self, texts: list[str]) -> list[dict[str, float]]:
        """Batch entry point: one POST per ``batch_size`` chunk of distinct uncached texts.

        Empty/whitespace and cache-hit texts are short-circuited. On ANY failure the whole
        batch degrades and returns lexical vectors for every text — never a mix of dense and
        lexical (invariant #3).
        """
        results: list[dict[str, float] | None] = [None] * len(texts)
        to_fetch: dict[str, list[int]] = {}
        with self._lock:
            degraded = self._degraded
            for i, text in enumerate(texts):
                key = text.strip()
                if degraded or not key:
                    results[i] = self._fallback.embed(text)
                    continue
                cached = self._cache.get(key)
                if cached is not None:
                    self._cache.move_to_end(key)
                    self.cache_hits += 1
                    results[i] = cached
                else:
                    self.cache_misses += 1
                    to_fetch.setdefault(key, []).append(i)

        if to_fetch:
            unique = list(to_fetch.keys())
            try:
                fetched = self._fetch_unique(unique)
            except Exception as exc:  # noqa: BLE001 — degrade the whole batch to lexical
                self._degrade(exc)
                return [self._fallback.embed(t) for t in texts]
            with self._lock:
                if self._degraded:
                    return [self._fallback.embed(t) for t in texts]
                for key, emb in zip(unique, fetched, strict=True):
                    self._cache_put(key, emb)
                    for idx in to_fetch[key]:
                        results[idx] = emb

        return [r if r is not None else self._fallback.embed("") for r in results]

    def _fetch_unique(self, unique: list[str]) -> list[dict[str, float]]:
        """Fetch dense vectors for distinct keys, chunked by ``batch_size``."""
        out: list[dict[str, float]] = []
        for start in range(0, len(unique), self.batch_size):
            chunk = unique[start : start + self.batch_size]
            sent = [t[: self.max_input_chars] for t in chunk]
            self.batch_count += 1
            vecs = self._request_with_retry(sent)
            out.extend({str(i): v for i, v in enumerate(vec)} for vec in vecs)
        return out

    # --- internal state mutation (locked) ------------------------------------

    def _cache_put(self, key: str, emb: dict[str, float]) -> None:
        self._cache[key] = emb
        self._cache.move_to_end(key)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)

    def _degrade(self, exc: Exception) -> None:
        with self._lock:
            if not self._degraded:
                self.degrades += 1
            self._degraded = True
            self._cache.clear()  # drop dense vectors so we never mix embedding spaces
        log.warning(
            "VoyageEmbedder degraded to BagOfWords: %s (%s); last_latency_ms=%.1f",
            type(exc).__name__,
            exc,
            self.last_latency_ms,
        )

    # --- observability -------------------------------------------------------

    @property
    def is_degraded(self) -> bool:
        with self._lock:
            return self._degraded

    def stats(self) -> dict[str, Any]:
        with self._lock:
            cache_len = len(self._cache)
            degraded = self._degraded
        return {
            "degraded": degraded,
            "embed_calls": self.embed_calls,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_size": cache_len,
            "api_calls": self.api_calls,
            "retries": self.retries,
            "degrades": self.degrades,
            "batch_count": self.batch_count,
            "last_latency_ms": round(self.last_latency_ms, 2),
            "total_latency_ms": round(self.total_latency_ms, 2),
        }


def _parse_retry_after(resp: httpx.Response) -> float | None:
    """Parse a numeric ``Retry-After`` header (seconds); ignore HTTP-date form."""
    value = resp.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
