"""Batch vs single-query consistency.

route_cascade (routing/learned_router.py) is the VECTORIZED cascade used for
all offline evaluation; RouterCore.route (webapp/router_core.py) is the LOOP
cascade the live API runs. They are two independent implementations of the same
rule. Any divergence means the offline-reported numbers do not describe what
the deployed API actually does - so we compare them query-by-query.
"""
import numpy as np
import pytest

from routing.config import MODELS
from routing.learned_router import make_X, route_cascade, sigmoid

PER_CLASS = 10


@pytest.fixture(scope="module")
def sample(test_queries):
    """~50 queries, balanced across all 5 capability classes."""
    by_class = {}
    for qid, text, cls in test_queries:
        by_class.setdefault(cls, []).append((qid, text, cls))
    out = []
    for cls in sorted(by_class):
        out.extend(by_class[cls][:PER_CLASS])
    return out


def test_sample_covers_all_classes(sample, core):
    classes = {s[2] for s in sample}
    assert classes == set(core.classes), "sample must span all 5 classes"
    # ~50 queries; a class with fewer than PER_CLASS held-out test rows simply
    # contributes what it has (measured: 46 on the current split).
    assert 40 <= len(sample) <= PER_CLASS * len(core.classes)


def test_batch_and_single_cascade_agree_on_every_query(core, sample):
    texts = [s[1] for s in sample]
    classes = [s[2] for s in sample]

    # OFFLINE / batch path: shared featurizer + vectorized cascade.
    # NOTE: make_X derives its one-hot width from the classes PRESENT in the
    # batch, so the batch must span all 5 classes - exactly how the offline
    # evaluation always calls it. `sample` satisfies that (asserted above).
    X, _idf = make_X(texts, classes, idf=core.idf, prior=core.prior)
    assert X.shape[1] == 2066
    P = sigmoid(X @ core.W + core.b)
    batch_idx = route_cascade(P, core.t_star)

    # ONLINE / single path: the exact code /api/route executes.
    single_idx = [core.route(t, c, core.t_star)["chosen_index"]
                  for t, c in zip(texts, classes)]

    mismatches = [
        f"{texts[i]!r} cls={classes[i]}: batch={MODELS[batch_idx[i]]} "
        f"single={MODELS[single_idx[i]]}"
        for i in range(len(texts))
        if int(batch_idx[i]) != single_idx[i]
    ]
    assert not mismatches, "cascade divergence:\n" + "\n".join(mismatches)


def test_batch_and_single_probabilities_agree(core, sample):
    """The featurizers must also agree, not just the final argmax. Uses the
    FULL sample so the batch spans all 5 classes (make_X precondition)."""
    texts = [s[1] for s in sample]
    classes = [s[2] for s in sample]
    X, _ = make_X(texts, classes, idf=core.idf, prior=core.prior)
    P = sigmoid(X @ core.W + core.b)
    for i, (t, c) in enumerate(zip(texts, classes)):
        d = core.route(t, c, core.t_star)
        online = np.array([d["p_correct"][m] for m in MODELS])
        # route() rounds to 4dp; compare at that precision
        assert np.allclose(online, np.round(P[i], 4), atol=1e-4), (
            f"probability mismatch for {t!r}"
        )


def test_featurizer_width_asymmetry_is_documented(core, sample):
    """RouterCore.featurize is width-stable for ANY single query (fixed class
    order), while the training helper make_X sizes its one-hot from the classes
    present in the batch. Pin both behaviours so the asymmetry stays deliberate:
    offline eval always batches all 5 classes; the live path never depends on
    batch composition."""
    # single query, any class -> always 2066
    for cls in core.classes:
        assert core.featurize("probe", cls).shape == (2066,)
    # a single-class BATCH through make_X is narrower (known, documented)
    coding = [s[1] for s in sample if s[2] == "Coding"][:4]
    X_narrow, _ = make_X(coding, ["Coding"] * len(coding),
                         idf=core.idf, prior=core.prior)
    assert X_narrow.shape[1] < 2066
    # ...while the same queries through the live featurizer stay at 2066
    for t in coding:
        assert core.featurize(t, "Coding").shape == (2066,)


def test_batch_cascade_matches_loop_on_synthetic_vectors(core):
    """Direct rule-level check on hand-built probability matrices."""
    cases = [
        # only 3rd cheapest clears
        np.array([[0.1, 0.2, 0.96, 0.99, 0.99, 0.99, 0.99, 0.99]]),
        # nothing clears -> strongest
        np.full((1, len(MODELS)), 0.05),
        # everything clears -> cheapest
        np.full((1, len(MODELS)), 0.999),
        # only strongest clears
        np.array([[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.97]]),
    ]
    for P in cases:
        batch = route_cascade(P, core.t_star)[0]
        # replicate the online loop rule by hand
        loop = len(MODELS) - 1
        for m in range(len(MODELS)):
            if P[0, m] >= core.t_star:
                loop = m
                break
        assert int(batch) == loop, f"P={P[0]} batch={batch} loop={loop}"
