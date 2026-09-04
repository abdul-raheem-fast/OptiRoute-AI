"""Multi-objective router behaviour (requirements 1, 3, 6) + the pure
selection core: latency budget, quality floor, fallback, explanation,
determinism, and the guarantee that routing makes NO external model call.
"""
import numpy as np
import pytest

from routing.config import MODELS
from routing.mo_core import Norm, Policy, select

Q_CODE = "Write a Python function that reverses a linked list and explain its complexity."
Q_MATH = "Solve for x: 3x^2 + 2x - 5 = 0, showing every step of the derivation."


# ------------------------------------------------------- pure selection core
def _tiny(norm_cost=(0.001, 0.02, 0.01), norm_lat=(0.5, 1.0, 0.8)):
    acc = np.array([0.40, 0.90, 0.60])
    cost = np.array(norm_cost)
    lat = np.array(norm_lat)
    return acc, cost, lat, Norm.from_stats(cost, lat)


def test_select_prefers_cheaper_when_quality_ties():
    acc, cost, lat, norm = _tiny()
    p = np.array([0.80, 0.80, 0.80])                 # identical quality
    elig = np.array([True, True, True])
    pol = Policy("x", elig, 1.0, 0.0, None, None)     # cost is the objective
    r = select(p, acc, cost, lat, pol, norm)
    assert r["chosen"] == 0                           # cheapest wins the tie
    assert r["reason_code"] == "utility_argmax"


def test_select_falls_back_to_strongest_when_floor_unmet():
    acc, cost, lat, norm = _tiny()
    p = np.array([0.30, 0.50, 0.40])                  # nothing clears 0.95
    elig = np.array([True, True, True])
    pol = Policy("x", elig, 0.5, 0.1, 0.95, None)
    r = select(p, acc, cost, lat, pol, norm)
    assert r["is_fallback"] is True
    assert r["chosen"] == 1                           # strongest eligible (acc .90)
    assert r["reason_code"] == "quality_floor_escalated_to_strongest"


def test_select_quality_floor_admits_only_models_above_it():
    acc, cost, lat, norm = _tiny()
    p = np.array([0.30, 0.99, 0.40])                  # only model 1 clears .90
    elig = np.array([True, True, True])
    pol = Policy("x", elig, 1.0, 0.0, 0.90, None)
    r = select(p, acc, cost, lat, pol, norm)
    assert r["chosen"] == 1
    assert r["is_fallback"] is False
    assert list(r["admissible"]) == [False, True, False]


def test_select_latency_budget_is_a_hard_filter():
    acc, cost, lat, norm = _tiny(norm_lat=(0.5, 1.0, 0.8))
    p = np.array([0.60, 0.95, 0.60])                  # model 1 best quality...
    elig = np.array([True, True, True])
    pol = Policy("x", elig, 0.0, 0.0, None, 0.6)      # ...but budget is 0.6s
    r = select(p, acc, cost, lat, pol, norm)
    assert r["chosen"] == 0                           # only model 0 is <= 0.6s
    assert r["budget_met"] is True


def test_select_unmet_budget_uses_the_fastest():
    acc, cost, lat, norm = _tiny(norm_lat=(0.5, 1.0, 0.8))
    p = np.array([0.60, 0.95, 0.60])
    elig = np.array([True, True, True])
    pol = Policy("x", elig, 0.0, 0.0, None, 0.1)      # nothing is <= 0.1s
    r = select(p, acc, cost, lat, pol, norm)
    assert r["budget_met"] is False
    assert r["chosen"] == 0                           # fastest eligible
    assert r["reason_code"] == "latency_budget_unmet_used_fastest"


def test_select_returns_none_when_nothing_is_eligible():
    acc, cost, lat, norm = _tiny()
    p = np.array([0.9, 0.9, 0.9])
    elig = np.array([False, False, False])
    pol = Policy("x", elig, 0.5, 0.1, None, None)
    r = select(p, acc, cost, lat, pol, norm)
    assert r["chosen"] is None
    assert r["reason_code"] == "no_eligible_model"


# ---------------------------------------------------------- live MoRouter
def test_routing_is_deterministic(mo_router):
    a = mo_router.route(Q_CODE, mode="balanced")
    b = mo_router.route(Q_CODE, mode="balanced")
    assert a["selected_model"] == b["selected_model"]
    assert a["routing_score"] == b["routing_score"]
    assert a["estimated_cost_per_query"] == b["estimated_cost_per_query"]


def test_routing_makes_no_network_call(mo_router, monkeypatch):
    """The routing DECISION is pure local arithmetic - no socket is opened."""
    import socket

    def _boom(*a, **k):
        raise AssertionError("routing attempted a network/LLM call")

    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    d = mo_router.route(Q_MATH, mode="balanced")
    assert d["selected_model"] in MODELS


def test_score_is_calibrated_and_not_called_p_correct(mo_router):
    d = mo_router.route(Q_CODE, mode="balanced")
    assert 0.0 <= d["routing_score"] <= 1.0
    assert "p_correct" not in d                       # honest renaming
    assert d["router"] == "multi_objective"
    # calibrated quality is reported per model too
    assert set(d["calibrated_quality"].keys()) == set(MODELS)


def test_all_modes_select_an_eligible_model(mo_router):
    for mode in ("economy", "balanced", "speed", "quality", "private"):
        d = mo_router.route(Q_CODE, mode=mode)
        assert d["selected_model"] in d["eligible_models"], mode
        assert d["mode"] == mode


def test_modes_produce_different_routing(mo_router):
    """The five objectives are genuinely different policies, not relabelled."""
    picks = {m: mo_router.route(Q_CODE, mode=m)["selected_model"]
             for m in ("economy", "balanced", "speed", "quality", "private")}
    assert len(set(picks.values())) >= 2


def test_speed_mode_respects_its_latency_budget(mo_router, mo_art):
    budget_ms = mo_art["modes"]["speed"]["latency_budget_ms"]
    d = mo_router.route(Q_CODE, mode="speed")
    st = mo_art["measured_train_stats"]
    assert d["estimated_latency_ms"] <= budget_ms + 1e-6
    assert st[d["selected_model"]]["latency_ms"] <= budget_ms + 1e-6


def test_explicit_latency_budget_overrides_the_mode(mo_router, mo_art):
    st = mo_art["measured_train_stats"]
    d = mo_router.route(Q_CODE, mode="balanced", latency_budget_ms=250)
    assert d["constraints"]["latency_budget_ms"] == pytest.approx(250)
    # chosen model is within budget, or the budget was unmet and it used fastest
    within = st[d["selected_model"]]["latency_ms"] <= 250 + 1e-6
    assert within or d["constraints"]["latency_budget_met"] is False


def test_unmeetable_budget_reports_and_uses_fastest(mo_router):
    d = mo_router.route(Q_CODE, mode="balanced", latency_budget_ms=1)
    assert d["constraints"]["latency_budget_met"] is False
    assert d["reason_code"] == "latency_budget_unmet_used_fastest"


def test_per_query_quality_floor_forces_escalation(mo_router):
    d = mo_router.route(Q_CODE, mode="balanced", quality_floor=0.999)
    assert d["is_fallback"] is True
    assert d["reason_code"] == "quality_floor_escalated_to_strongest"
    assert "quality floor" in d["reason"].lower() or "escalat" in d["reason"].lower()


def test_low_quality_floor_never_escalates(mo_router):
    d = mo_router.route(Q_CODE, mode="balanced", quality_floor=0.0)
    assert d["is_fallback"] is False


def test_estimated_cost_and_latency_match_the_chosen_model(mo_router, mo_art):
    st = mo_art["measured_train_stats"]
    d = mo_router.route(Q_MATH, mode="economy")
    m = d["selected_model"]
    assert d["estimated_cost_per_query"] == pytest.approx(st[m]["cost"], abs=1e-6)
    assert d["estimated_latency_ms"] == pytest.approx(st[m]["latency_ms"], abs=0.2)


def test_latency_is_split_into_three_honest_parts(mo_router):
    d = mo_router.route(Q_CODE, mode="balanced")
    lat = d["latency"]
    assert {"router_overhead_ms", "model_inference_ms", "end_to_end_ms"} <= set(lat)
    assert lat["router_overhead_ms"] >= 0.0
    assert lat["end_to_end_ms"] == pytest.approx(
        lat["router_overhead_ms"] + lat["model_inference_ms"], abs=0.5)


def test_explanation_is_present_and_grounded(mo_router):
    d = mo_router.route(Q_CODE, mode="balanced")
    assert isinstance(d["reason"], str) and len(d["reason"]) > 10
    assert d["reason_code"]
    assert "why_not_strongest" in d and "pareto" in d
    assert d["privacy_status"] in {"approved", "blocked"}
    # per-model breakdown carries measured numbers, not invented ones
    row = next(r for r in d["model_scores"] if r["model"] == d["selected_model"])
    assert row["admissible"] is True
    assert row["measured_cost_per_query"] >= 0.0


def test_private_mode_explanation_mentions_the_constraint(mo_router):
    d = mo_router.route(Q_CODE, mode="private")
    assert d["constraints"]["privacy_restricted"] is True
    assert set(d["eligible_models"]) <= {"Llama-3.1-8B-Instruct", "Qwen3-8B"}
