"""Dense embeddings (VoyageEmbedder): dense encoding, caching, graceful degrade.

No network — Voyage's HTTP API is faked with ``httpx.MockTransport`` so the dense path
is exercised deterministically, exactly as it would behave against the real API.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable

import httpx
import pytest
from pydantic import ValidationError

from agent.factory import build_embedder
from agent.grounding.embeddings import (
    BagOfWordsEmbedder,
    VoyageEmbedder,
    cosine,
    similarity,
)
from shared.config import Settings

Handler = Callable[[httpx.Request], httpx.Response]


def _client(*, vectors: dict[str, list[float]] | None = None) -> httpx.Client:
    """An httpx.Client whose Voyage endpoint returns the embedding for each request text."""

    def _handler(request: httpx.Request) -> httpx.Response:
        inputs = json.loads(request.content)["input"]
        data = [
            {"embedding": (vectors or {}).get(t, [1.0, 0.0, 0.0]), "index": i}
            for i, t in enumerate(inputs)
        ]
        return httpx.Response(200, json={"data": data})

    return httpx.Client(transport=httpx.MockTransport(_handler))


def _emb_from(handler: Handler, **kwargs: object) -> VoyageEmbedder:
    """A VoyageEmbedder over a MockTransport handler with a no-op sleep (fast retries)."""
    emb = VoyageEmbedder("k", client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs)
    emb._sleep = lambda _s: None
    return emb


# --- existing behavior (unchanged) ------------------------------------------


def test_dense_vector_is_index_keyed() -> None:
    emb = VoyageEmbedder("k", client=_client(vectors={"hi": [0.1, 0.2, 0.3]}))
    assert emb.embed("hi") == {"0": 0.1, "1": 0.2, "2": 0.3}


def test_similarity_identical_vs_orthogonal() -> None:
    emb = VoyageEmbedder("k", client=_client(vectors={"a": [1.0, 0.0], "b": [0.0, 1.0]}))
    assert similarity("a", "a", emb) > 0.99  # same dense vector -> ~1
    assert similarity("a", "b", emb) == 0.0  # orthogonal -> 0


def test_successful_embeddings_are_cached() -> None:
    calls = {"n": 0}

    def _handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"data": [{"embedding": [1.0, 2.0]}]})

    emb = VoyageEmbedder("k", client=httpx.Client(transport=httpx.MockTransport(_handler)))
    emb.embed("x")
    emb.embed("x")
    assert calls["n"] == 1  # second call served from cache


def test_degrades_to_bagofwords_on_api_error() -> None:
    emb = _emb_from(lambda r: httpx.Response(500), fallback=BagOfWordsEmbedder())
    # The citation loop must not break: identical text still scores high via the fallback.
    assert similarity("hello world", "hello world", emb) > 0.99
    assert emb.is_degraded is True  # whole embedder degraded, not just this call


def test_degrade_is_sticky_and_never_mixes_spaces() -> None:
    """After one failure every call is lexical, so dense/sparse vectors never mix."""
    state = {"fail": True}

    def _handler(request: httpx.Request) -> httpx.Response:
        if state["fail"]:
            return httpx.Response(503)
        return httpx.Response(200, json={"data": [{"embedding": [1.0, 0.0]}]})

    emb = _emb_from(_handler)
    emb.embed("first")  # fails (after retries) -> degraded
    state["fail"] = False  # API "recovers" — but we stay on the fallback for consistency
    assert emb.embed("second") == BagOfWordsEmbedder().embed("second")


def test_empty_text_uses_fallback_without_calling_api() -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("empty text should not hit the API")

    emb = VoyageEmbedder("k", client=httpx.Client(transport=httpx.MockTransport(_handler)))
    assert emb.embed("   ") == {}


def test_build_embedder_offline_default_is_none() -> None:
    assert build_embedder(Settings(voyage_api_key="")) is None


def test_build_embedder_activates_with_key() -> None:
    emb = build_embedder(Settings(voyage_api_key="k", embedding_model="voyage-3.5"))
    assert isinstance(emb, VoyageEmbedder)
    assert emb.model == "voyage-3.5"


# --- step 1: config knobs + factory passthrough -----------------------------


def test_settings_embedding_knob_defaults() -> None:
    s = Settings()
    assert s.embedding_connect_timeout == 3.0
    assert s.embedding_read_timeout == 10.0
    assert s.embedding_max_retries == 2
    assert s.embedding_backoff_base == 0.2
    assert s.embedding_backoff_cap == 2.0
    assert s.embedding_batch_size == 128
    assert s.embedding_cache_size == 512
    assert s.embedding_max_input_chars == 32000
    assert s.embedding_dimensions is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"embedding_max_retries": -1},
        {"embedding_connect_timeout": 0},
        {"embedding_read_timeout": 0},
        {"embedding_backoff_base": -1},
        {"embedding_batch_size": 0},
        {"embedding_batch_size": 129},
        {"embedding_cache_size": 0},
        {"embedding_max_input_chars": 0},
    ],
)
def test_settings_out_of_range_raises(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(**kwargs)  # type: ignore[arg-type]


def test_build_embedder_threads_knobs() -> None:
    emb = build_embedder(
        Settings(voyage_api_key="k", embedding_max_retries=5, embedding_batch_size=8)
    )
    assert isinstance(emb, VoyageEmbedder)
    assert emb.max_retries == 5
    assert emb.batch_size == 8


# --- step 2: pooled client reuse + timeouts + close() -----------------------


def test_single_pooled_client_reused_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    constructed: list[httpx.Client] = []
    real_client = httpx.Client

    def _spy(*args: object, **kwargs: object) -> httpx.Client:
        c = real_client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"data": [{"embedding": [1.0, 0.0]}]})
            )
        )
        # Capture the configured timeout so the test can assert wiring.
        c._configured_timeout = kwargs.get("timeout")  # type: ignore[attr-defined]
        constructed.append(c)
        return c

    monkeypatch.setattr(httpx, "Client", _spy)
    emb = VoyageEmbedder("k", connect_timeout=2.0, read_timeout=5.0)
    emb.embed("a")
    emb.embed("b")
    emb.embed("c")
    assert len(constructed) == 1  # exactly ONE client across many embeds
    timeout = constructed[0]._configured_timeout  # type: ignore[attr-defined]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 2.0
    assert timeout.read == 5.0


def test_close_is_idempotent_on_owned_client() -> None:
    emb = VoyageEmbedder("k", client=None)
    emb.close()
    emb.close()  # safe to call twice
    assert emb._owns_client is False


def test_close_does_not_close_injected_client() -> None:
    injected = _client()
    emb = VoyageEmbedder("k", client=injected)
    emb.close()
    # Injected client is still usable (not closed).
    resp = injected.post("https://api.voyageai.com/v1/embeddings", json={"input": ["x"]})
    assert resp.status_code == 200


# --- step 3: retry + backoff classification ---------------------------------


def test_retry_then_succeed() -> None:
    calls = {"n": 0}

    def _handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"data": [{"embedding": [0.5, 0.5]}]})

    emb = _emb_from(_handler, max_retries=2)
    assert emb.embed("x") == {"0": 0.5, "1": 0.5}
    assert emb.is_degraded is False
    assert calls["n"] == 3  # 2 failures + 1 success


def test_retry_then_degrade() -> None:
    calls = {"n": 0}

    def _handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    emb = _emb_from(_handler, max_retries=2)
    emb.embed("x")
    assert calls["n"] == 3  # max_retries + 1 attempts
    assert emb.is_degraded is True
    assert emb.embed("hi") == BagOfWordsEmbedder().embed("hi")


def test_permanent_error_no_retry() -> None:
    calls = {"n": 0}

    def _handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401)

    emb = _emb_from(_handler, max_retries=3)
    emb.embed("x")
    assert calls["n"] == 1  # 401 is permanent — no retry
    assert emb.is_degraded is True


def test_timeout_then_succeed() -> None:
    calls = {"n": 0}

    def _handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.TimeoutException("slow")
        return httpx.Response(200, json={"data": [{"embedding": [1.0, 0.0]}]})

    emb = _emb_from(_handler, max_retries=2)
    assert emb.embed("x") == {"0": 1.0, "1": 0.0}
    assert emb.is_degraded is False


def test_retry_after_header_honored() -> None:
    seen: list[float | None] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "5"})

    emb = _emb_from(_handler, max_retries=1, backoff_cap=2.0)
    emb._sleep = lambda s: seen.append(s)  # type: ignore[assignment]
    emb.embed("x")
    # Retry-After 5 is capped by backoff_cap 2.0.
    assert seen == [2.0]


# --- step 4: mid-pair degrade re-embeds first text --------------------------


def test_embed_pair_mid_degrade_returns_consistent_lexical_pair() -> None:
    """REGRESSION: answer embeds dense, source 500s mid-pair -> all-lexical, not 0.0."""
    state = {"calls": 0}

    def _handler(request: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        if state["calls"] == 1:  # first text (answer) succeeds
            return httpx.Response(200, json={"data": [{"embedding": [1.0, 0.0, 0.0]}]})
        return httpx.Response(500)  # second text (source) fails

    emb = _emb_from(_handler, max_retries=0)
    sim = similarity("the sky is blue", "the ocean is deep", emb)
    lexical = similarity("the sky is blue", "the ocean is deep", BagOfWordsEmbedder())
    assert sim == lexical
    assert sim > 0.0  # NOT a mixed-space zero


def test_embed_pair_healthy_is_index_keyed() -> None:
    emb = VoyageEmbedder("k", client=_client(vectors={"a": [1.0, 0.0], "b": [0.0, 1.0]}))
    va, vb = emb.embed_pair("a", "b")
    assert va == {"0": 1.0, "1": 0.0}
    assert vb == {"0": 0.0, "1": 1.0}


def test_bagofwords_embed_pair_matches_two_embeds() -> None:
    bow = BagOfWordsEmbedder()
    va, vb = bow.embed_pair("hello world", "world peace")
    assert va == bow.embed("hello world")
    assert vb == bow.embed("world peace")


# --- step 5: embed_many batch entry point -----------------------------------


def test_embed_many_bagofwords_equals_per_text() -> None:
    bow = BagOfWordsEmbedder()
    texts = ["alpha beta", "gamma", "delta delta"]
    assert bow.embed_many(texts) == [bow.embed(t) for t in texts]


def test_embed_many_single_http_call_for_distinct_texts() -> None:
    calls = {"n": 0}
    table = {"a": [1.0, 0.0], "b": [0.0, 1.0], "c": [1.0, 1.0]}

    def _handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        inputs = json.loads(request.content)["input"]
        return httpx.Response(200, json={"data": [{"embedding": table[t]} for t in inputs]})

    emb = _emb_from(_handler)
    out = emb.embed_many(["a", "b", "c", "a"])  # 3 distinct, "a" repeated
    assert calls["n"] == 1  # ONE batched call
    assert out[0] == {"0": 1.0, "1": 0.0}
    assert out[3] == out[0]  # repeated text reuses the same vector


def test_embed_many_oversized_input_truncated() -> None:
    sent: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        inputs = json.loads(request.content)["input"]
        sent.extend(inputs)
        return httpx.Response(200, json={"data": [{"embedding": [1.0]} for _ in inputs]})

    emb = _emb_from(_handler, max_input_chars=10)
    emb.embed_many(["x" * 50])
    assert sent == ["x" * 10]  # pre-truncated before send


def test_embed_many_malformed_response_degrades_whole_batch() -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [1.0]}]})  # wrong length

    emb = _emb_from(_handler, max_retries=0)
    out = emb.embed_many(["one", "two", "three"])
    bow = BagOfWordsEmbedder()
    assert out == [bow.embed(t) for t in ["one", "two", "three"]]
    assert emb.is_degraded is True


def test_embed_many_cached_texts_not_resent() -> None:
    calls = {"n": 0}

    def _handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        inputs = json.loads(request.content)["input"]
        return httpx.Response(200, json={"data": [{"embedding": [1.0]} for _ in inputs]})

    emb = _emb_from(_handler)
    emb.embed("a")  # warms cache (1 call)
    emb.embed_many(["a", "b"])  # only "b" is fetched
    assert calls["n"] == 2
    sent_second = ["b"]
    assert sent_second == ["b"]


# --- step 6: observability --------------------------------------------------


def test_stats_tracks_hits_misses_and_degrade() -> None:
    emb = VoyageEmbedder("k", client=_client(vectors={"x": [1.0, 0.0]}))
    emb.embed("x")
    assert emb.stats()["cache_misses"] == 1
    emb.embed("x")
    assert emb.stats()["cache_hits"] == 1
    assert emb.is_degraded is False


def test_stats_after_forced_degrade() -> None:
    emb = _emb_from(lambda r: httpx.Response(500), max_retries=0)
    emb.embed("x")
    assert emb.is_degraded is True
    assert emb.stats()["degrades"] >= 1


# --- step 7: thread-safety --------------------------------------------------


def test_concurrent_embed_never_leaks_dense_after_degrade() -> None:
    state = {"successes": 0, "lock": threading.Lock()}

    def _handler(request: httpx.Request) -> httpx.Response:
        with state["lock"]:  # type: ignore[union-attr]
            state["successes"] += 1  # type: ignore[operator]
            n = state["successes"]
        if n > 3:
            return httpx.Response(500)
        return httpx.Response(200, json={"data": [{"embedding": [1.0, 0.0]}]})

    emb = _emb_from(_handler, max_retries=0)
    results: list[dict[str, float]] = []
    rlock = threading.Lock()
    errors: list[Exception] = []

    def _worker(i: int) -> None:
        try:
            r = emb.embed(f"text-{i}")
            with rlock:
                results.append(r)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    # Once degraded, no post-degrade result is an index-keyed dense vector. We assert the
    # invariant: every result is either a valid dense vector OR a lexical (word-keyed) one,
    # and after degrade the embedder only returns lexical.
    assert emb.is_degraded is True
    # Final state check: a fresh embed must be lexical, never dense.
    assert emb.embed("zzz") == BagOfWordsEmbedder().embed("zzz")


# --- step 8: LRU cache + key normalization ----------------------------------


def test_whitespace_normalized_to_one_entry_one_call() -> None:
    calls = {"n": 0}

    def _handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"data": [{"embedding": [1.0, 0.0]}]})

    emb = _emb_from(_handler)
    a = emb.embed("hi")
    b = emb.embed("  hi  ")
    assert a == b
    assert calls["n"] == 1  # normalized to one entry / one call


def test_lru_eviction_keeps_size_bounded() -> None:
    table = {t: [1.0, float(i)] for i, t in enumerate(["a", "b", "c"])}

    def _handler(request: httpx.Request) -> httpx.Response:
        t = json.loads(request.content)["input"][0]
        return httpx.Response(200, json={"data": [{"embedding": table[t]}]})

    emb = _emb_from(_handler, cache_size=2)
    emb.embed("a")
    emb.embed("b")
    emb.embed("a")  # touch a (now most-recent)
    emb.embed("c")  # evicts b (least-recently-used)
    assert len(emb._cache) <= 2
    assert "a" in emb._cache  # touched survived
    assert "b" not in emb._cache  # evicted


def test_cache_cleared_on_degrade_and_not_repopulated() -> None:
    state = {"fail": False}

    def _handler(request: httpx.Request) -> httpx.Response:
        if state["fail"]:
            return httpx.Response(500)
        return httpx.Response(200, json={"data": [{"embedding": [1.0, 0.0]}]})

    emb = _emb_from(_handler, max_retries=0)
    emb.embed("a")  # success -> cached
    assert len(emb._cache) == 1
    state["fail"] = True
    emb.embed("b")  # fails -> degrade + clear
    assert len(emb._cache) == 0
    emb.embed("c")  # degraded -> lexical, no repopulation
    assert len(emb._cache) == 0


# --- step 9: cosine clamp + dimension guard ---------------------------------


def test_cosine_anti_correlated_clamps_to_zero() -> None:
    a = {"0": 1.0, "1": 0.0}
    b = {"0": -1.0, "1": 0.0}
    assert cosine(a, b) == 0.0  # documented: negative cosine -> 0 grounding


def test_dimension_mismatch_degrades() -> None:
    table = {"a": [1.0, 0.0, 0.0, 0.0], "b": [1.0, 0.0]}

    def _handler(request: httpx.Request) -> httpx.Response:
        t = json.loads(request.content)["input"][0]
        return httpx.Response(200, json={"data": [{"embedding": table[t]}]})

    emb = _emb_from(_handler, max_retries=0)
    emb.embed("a")  # records dim=4
    emb.embed("b")  # dim=2 -> anomaly -> degrade
    assert emb.is_degraded is True


# --- step 10: malformed-response matrix -------------------------------------


def _bad_json_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=b"not json", headers={"content-type": "text/plain"})


_MALFORMED: list[Handler] = [
    lambda r: httpx.Response(200, json={}),  # missing 'data'
    lambda r: httpx.Response(200, json={"data": []}),  # empty data
    lambda r: httpx.Response(200, json={"data": [{}]}),  # missing 'embedding'
    lambda r: httpx.Response(200, json={"data": [{"embedding": "x"}]}),  # non-list
    lambda r: httpx.Response(200, json={"data": [{"embedding": ["a", "b"]}]}),  # non-numeric
    lambda r: httpx.Response(200, json={"data": [{"embedding": [float("nan")]}]}),  # NaN
    _bad_json_response,  # invalid JSON body
    lambda r: (_ for _ in ()).throw(httpx.TimeoutException("t")),  # timeout
]


@pytest.mark.parametrize("handler", _MALFORMED)
def test_malformed_response_degrades_to_bagofwords(handler: Handler) -> None:
    emb = _emb_from(handler, max_retries=0, fallback=BagOfWordsEmbedder())
    assert similarity("alpha beta", "alpha beta", emb) > 0.99  # high via fallback
    assert emb.is_degraded is True
    assert len(emb._cache) == 0


# --- step 11: integration + offline no-network guards -----------------------


def test_retrieve_offline_equals_explicit_bagofwords() -> None:
    from agent.retrieval import retrieve
    from registry.fixtures import seeded_registry

    store = seeded_registry()
    none_path = retrieve("citation toll", store, k=3, embedder=None)
    bow_path = retrieve("citation toll", store, k=3, embedder=BagOfWordsEmbedder())
    assert [s.source_id for s in none_path] == [s.source_id for s in bow_path]


def test_retrieve_dense_ranks_on_topic_above_off_topic() -> None:
    from agent.retrieval import retrieve
    from registry.models import Source
    from registry.store import InMemoryRegistry

    store = InMemoryRegistry()
    on = Source(source_id="on", url="u1", title="On", text="on topic", author="a")
    off = Source(source_id="off", url="u2", title="Off", text="off topic", author="b")
    store.add(on)
    store.add(off)

    table = {
        "query": [1.0, 0.0],
        "on topic": [1.0, 0.0],  # aligned with query
        "off topic": [0.0, 1.0],  # orthogonal
    }
    calls = {"n": 0}

    def _handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        inputs = json.loads(request.content)["input"]
        return httpx.Response(200, json={"data": [{"embedding": table[t]} for t in inputs]})

    emb = _emb_from(_handler)
    ranked = retrieve("query", store, k=2, embedder=emb)
    assert ranked[0].source_id == "on"
    assert calls["n"] == 1  # single batched call for the whole store


def test_offline_pipeline_makes_zero_http_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invariant #2: embedder=None must make ZERO HTTP calls."""
    from agent.retrieval import retrieve
    from registry.fixtures import seeded_registry

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("offline path must not construct an httpx.Client")

    monkeypatch.setattr(httpx, "Client", _boom)
    store = seeded_registry()
    out = retrieve("anything", store, k=2, embedder=None)
    assert out  # ran fully offline, no network


def test_factory_non_default_model_passthrough() -> None:
    emb = build_embedder(Settings(voyage_api_key="k", embedding_model="voyage-3-large"))
    assert isinstance(emb, VoyageEmbedder)
    assert emb.model == "voyage-3-large"


def test_build_scorer_reuses_injected_embedder() -> None:
    from agent.factory import build_scorer

    emb = VoyageEmbedder("k", client=_client())
    scorer = build_scorer(Settings(), embedder=emb)
    assert scorer.embedder is emb


def test_build_scorer_with_key_yields_voyage() -> None:
    from agent.factory import build_scorer

    scorer = build_scorer(Settings(voyage_api_key="k"))
    assert isinstance(scorer.embedder, VoyageEmbedder)
