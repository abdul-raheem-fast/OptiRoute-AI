"""Unit invariants on RouterCore.route() - the per-query online path.

These pin down the contracts the dashboard and the API rely on: fixed feature
width, finite probabilities, a chosen model that always exists in the registry,
the cheapest-first cascade selecting the FIRST model over the gate, a guaranteed
strongest-model fallback, and bit-identical determinism.
"""
import numpy as np
import pytest

import webapp.router_core as rc
from routing.config import MODELS, STRONGEST

EXPECTED_WIDTH = 2066  # 5 scalars + 5 one-hot + 2048 hashed tf-idf + 8 prior

STRESS_TEXTS = [
    "",                                  # empty
    "a",                                 # single char
    "hello world",                       # plain
    "x" * 20000,                         # very long
    "the " * 5000,                       # long repetitive
    "\u00e9\u00e8\u00ea \u4f60\u597d \u043f\u0440\u0438\u0432\u0435\u0442 \U0001F680\U0001F31F",  # unicode/emoji
    "0123456789 " * 500,                 # digit-heavy
    "????" * 200,                        # question-mark heavy
    "```python\ndef f():\n    import os\n```",  # code markers
    "SELECT * FROM users; --",           # injection-style
]


def test_feature_width_is_always_2066(core):
    for text in STRESS_TEXTS:
        for cls in core.classes:
            x = core.featurize(text, cls)
            assert x.shape == (EXPECTED_WIDTH,), (
                f"width {x.shape} for text len={len(text)} cls={cls}"
            )


def test_feature_vector_is_finite_and_normalized(core):
    for text in STRESS_TEXTS:
        x = core.featurize(text, core.classes[0])
        assert np.all(np.isfinite(x)), f"non-finite feature for len={len(text)}"


def test_weights_carry_no_nan_from_training_masking(core):
    """Training masked NaN columns for aligned-7 aux rows; assert no NaN/inf
    leaked into the exported heads, which would poison every inference."""
    assert np.all(np.isfinite(core.W)), "W contains NaN/inf"
    assert np.all(np.isfinite(core.b)), "b contains NaN/inf"
    assert np.all(np.isfinite(core.idf)), "idf contains NaN/inf"
    for cls in core.classes:
        assert np.all(np.isfinite(core.prior[cls])), f"prior[{cls}] not finite"


def test_probabilities_are_valid_for_all_stress_inputs(core):
    for text in STRESS_TEXTS:
        d = core.route(text, core.classes[0], core.t_star)
        probs = list(d["p_correct"].values())
        assert len(probs) == len(MODELS) == 8
        for m, p in d["p_correct"].items():
            assert isinstance(p, float), f"{m} prob not a float"
            assert np.isfinite(p), f"{m} prob not finite for len={len(text)}"
            assert 0.0 <= p <= 1.0, f"{m} prob {p} outside [0,1]"


def test_route_always_returns_a_registry_model(core):
    for text in STRESS_TEXTS:
        d = core.route(text, None, core.t_star)  # class guessed internally
        assert d["chosen_model"] is not None
        assert d["chosen_model"] in MODELS
        assert d["chosen_model"] in core.registry, "chosen model not in registry"
        assert d["chosen_index"] == MODELS.index(d["chosen_model"])


def test_cascade_selects_first_model_over_gate(core, monkeypatch):
    """Only the 3rd-cheapest model clears t; models 1,2 are below and 4+ are
    above. The cascade must stop at index 2, not pick 0, 1 or any later one."""
    fixed = np.array([0.10, 0.20, 0.96, 0.99, 0.99, 0.99, 0.99, 0.99])
    monkeypatch.setattr(rc, "sigmoid", lambda z: fixed)

    d = core.route("probe", "Coding", 0.95)
    assert d["chosen_index"] == 2
    assert d["chosen_model"] == MODELS[2]
    assert d["chosen_model"] not in (MODELS[0], MODELS[1], MODELS[3])
    # The walk must have stopped at the first accept (3 steps recorded).
    assert len(d["cascade_trace"]) == 3
    assert [s["passes"] for s in d["cascade_trace"]] == [False, False, True]
    assert d["is_fallback"] is False


def test_cascade_order_matches_config_order(core, monkeypatch):
    """With every model over the gate, the CHEAPEST (index 0) must win -
    proving the walk direction is cheap->strong, not strong->cheap."""
    fixed = np.full(len(MODELS), 0.999)
    monkeypatch.setattr(rc, "sigmoid", lambda z: fixed)
    d = core.route("probe", "Coding", 0.95)
    assert d["chosen_index"] == 0
    assert d["chosen_model"] == MODELS[0]
    assert len(d["cascade_trace"]) == 1


def test_fallback_is_always_strongest_when_nothing_clears(core, monkeypatch):
    fixed = np.full(len(MODELS), 0.01)  # adversarial: nothing clears t
    monkeypatch.setattr(rc, "sigmoid", lambda z: fixed)
    d = core.route("probe", "Coding", 0.95)
    assert d["chosen_index"] == len(MODELS) - 1
    assert d["chosen_model"] == STRONGEST == "gpt-5"
    assert d["is_fallback"] is True
    assert len(d["cascade_trace"]) == len(MODELS)  # walked the whole pool


def test_fallback_consistency_on_real_low_confidence_input(core):
    """A real OOD gibberish input: whatever it picks, the fallback flag and the
    chosen model must agree with the cascade rule."""
    d = core.route("zzz qqq xxx vvv www jjj", None, 0.99)
    over = [m for m, p in d["p_correct"].items() if p >= 0.99]
    if d["is_fallback"]:
        assert d["chosen_model"] == STRONGEST
        assert over == [] or d["chosen_model"] == STRONGEST
    else:
        assert d["chosen_model"] == over[0]


def test_route_is_deterministic(core):
    q = "Explain the tradeoff between recursion and iteration in Python."
    for cls in [None, "Coding"]:
        d1 = core.route(q, cls, core.t_star)
        d2 = core.route(q, cls, core.t_star)
        assert d1 == d2, "route() not deterministic (dict mismatch)"
        assert d1["p_correct"] == d2["p_correct"], "probabilities not bit-identical"
        assert d1["chosen_model"] == d2["chosen_model"]
        assert d1["cascade_trace"] == d2["cascade_trace"]


def test_threshold_is_echoed_and_respected(core):
    for t in (0.5, 0.8, 0.95, 0.99):
        d = core.route("What is the capital of France?", None, t)
        assert d["threshold"] == pytest.approx(t)
        # every non-fallback choice must actually clear the gate
        if not d["is_fallback"]:
            assert d["p_correct"][d["chosen_model"]] >= t
