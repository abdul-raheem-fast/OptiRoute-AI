"""Shared fixtures for the OptiRoute AI correctness suite.

Everything here is read-only verification: no routing logic, weights or
business behaviour is modified. Fixtures expose the exact same data loaders
the production code uses (routing.splits.load_splits, the routing_matrix
pivots) so a parity failure can only mean the router disagrees with its own
frozen evaluation, never that the test loaded different data.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from routing.config import MODELS, OUT_DIR  # noqa: E402
from routing.splits import load_splits  # noqa: E402
from webapp.router_core import RouterCore  # noqa: E402


@pytest.fixture(scope="session")
def core():
    """The production inference core, loaded once for the whole session."""
    return RouterCore()


@pytest.fixture(scope="session")
def mo_art():
    """The fitted multi-objective artifact (skips if it has not been built)."""
    import json

    path = OUT_DIR.parent / "models" / "mo_objectives.json"
    if not path.exists():
        pytest.skip("mo_objectives.json not built - run: python -m routing.tune_mo")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def mo_router(core, mo_art):
    """The live multi-objective router, sharing the frozen inference core."""
    from webapp.mo_router import MoRouter

    return MoRouter(core=core)


@pytest.fixture(scope="session")
def server_mod():
    import webapp.server as mod

    return mod


@pytest.fixture(scope="session")
def client(server_mod):
    """In-process ASGI client - exercises the real FastAPI app, no sockets."""
    from fastapi.testclient import TestClient

    with TestClient(server_mod.app) as c:
        yield c


@pytest.fixture(scope="session")
def splits():
    """Official stratified splits (seed 42) - identical to learned_router.py."""
    tr, va, te, tier = load_splits()
    return {"train": tr, "val": va, "test": te, "tier": tier}


@pytest.fixture(scope="session")
def matrix():
    """query x model correct/cost/latency pivots, ordered by config.MODELS."""
    m = pd.read_csv(OUT_DIR / "routing_matrix.csv")
    meta = (
        pd.read_csv(OUT_DIR / "query_meta.csv")
        .drop_duplicates("query_id")
        .set_index("query_id")
    )
    K = m.pivot(index="query_id", columns="model_name", values="correct")[MODELS]
    C = m.pivot(index="query_id", columns="model_name", values="cost")[MODELS]
    L = m.pivot(index="query_id", columns="model_name", values="latency")[MODELS]
    return {"K": K, "C": C, "L": L, "meta": meta}


@pytest.fixture(scope="session")
def test_queries(splits, matrix):
    """(query_id, text, class) for every held-out test-split row."""
    meta = matrix["meta"]
    out = []
    for qid in splits["test"]:
        if qid not in meta.index:
            continue
        row = meta.loc[qid]
        out.append((qid, row["origin_query"], row["dataset_name"]))
    return out


def pct(values, q):
    """Simple percentile helper (no scipy dependency)."""
    arr = np.asarray(sorted(values), dtype=float)
    if arr.size == 0:
        return float("nan")
    k = (arr.size - 1) * q
    f = int(np.floor(k))
    c = int(np.ceil(k))
    if f == c:
        return float(arr[int(k)])
    return float(arr[f] + (arr[c] - arr[f]) * (k - f))
