"""Latency and load sanity for POST /api/route.

The endpoint is a pure in-memory weight lookup (no model APIs), so per-request
latency should be dominated by TF-IDF featurization of the query text. Two real
bugs this guards against:
  1. reloading the .npz weights or idf vector on every request (would show up
     as both a latency floor and monotonic memory growth), and
  2. unbounded growth of the session telemetry structures.
"""
import inspect
import time
import tracemalloc

import pytest

from conftest import pct
from webapp.router_core import RouterCore

N_REQUESTS = 100
# Local in-process ASGI calls; generous but meaningful for a weight lookup.
P50_BOUND_MS = 100.0
P95_BOUND_MS = 150.0
P99_BOUND_MS = 200.0
# Traced-Python-memory growth allowed across the whole burst. A per-request
# weights reload would add ~0.14 MB * 100 = ~14 MB and trip this.
MEM_GROWTH_BOUND_MB = 8.0


@pytest.fixture(scope="module")
def latencies(client, test_queries):
    queries = [q[1] for q in test_queries[:N_REQUESTS]]
    assert len(queries) == N_REQUESTS
    times = []
    for q in queries:
        t0 = time.perf_counter()
        r = client.post("/api/route", json={"query": q})
        times.append((time.perf_counter() - t0) * 1000.0)
        assert r.status_code == 200
    return times


def test_latency_bounds(latencies):
    p50, p95, p99 = (pct(latencies, q) for q in (0.50, 0.95, 0.99))
    print(f"\n--- /api/route latency over {len(latencies)} requests ---")
    print(f"p50={p50:.1f}ms  p95={p95:.1f}ms  p99={p99:.1f}ms  "
          f"max={max(latencies):.1f}ms")
    assert p50 < P50_BOUND_MS, f"p50 {p50:.1f}ms >= {P50_BOUND_MS}ms"
    assert p95 < P95_BOUND_MS, f"p95 {p95:.1f}ms >= {P95_BOUND_MS}ms"
    assert p99 < P99_BOUND_MS, f"p99 {p99:.1f}ms >= {P99_BOUND_MS}ms"


def test_weights_are_loaded_once_not_per_request(core, server_mod):
    """Structural guard: the hot path must not touch disk. If np.load / open
    ever appears inside route()/featurize(), weights or idf are being reloaded
    per request - a real bug, independent of what the latency numbers say."""
    for fn in (RouterCore.route, RouterCore.featurize,
               RouterCore._tfidf_one, RouterCore._scalars_one):
        src = inspect.getsource(fn)
        assert "np.load" not in src, f"{fn.__name__} reloads weights per call"
        assert "open(" not in src, f"{fn.__name__} reads a file per call"
    # The server holds exactly one shared core instance.
    assert isinstance(server_mod.core, RouterCore)
    assert server_mod.core is core or isinstance(server_mod.core, RouterCore)
    # idf / W are attributes loaded at __init__, present without any reload
    assert core.idf is not None and core.W is not None


def test_session_structures_stay_bounded(server_mod, latencies):
    """Telemetry must not grow without limit across the burst."""
    assert server_mod.session_log.maxlen == 500
    assert len(server_mod.session_log) <= 500
    allowed = set(server_mod.core.models) | {
        "_total", "_saved", "_esc", "_tier_easy", "_tier_medium", "_tier_hard"
    }
    assert set(server_mod.session.keys()) <= allowed, "unbounded session keys"


def test_no_memory_growth_across_burst(client, test_queries):
    queries = [q[1] for q in test_queries[:N_REQUESTS]]
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    for q in queries:
        client.post("/api/route", json={"query": q})
    after = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    growth_mb = (after - before) / 1e6
    print(f"\n--- traced memory growth over {len(queries)} requests: "
          f"{growth_mb:.2f} MB ---")
    assert growth_mb < MEM_GROWTH_BOUND_MB, (
        f"memory grew {growth_mb:.2f} MB across {len(queries)} requests - "
        "possible per-request reload or leak"
    )
