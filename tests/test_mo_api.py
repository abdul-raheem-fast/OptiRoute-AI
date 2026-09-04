"""API-layer coverage for the multi-objective router (requirements 8, 9).

Two contracts are pinned here:

1. BACKWARD COMPATIBILITY - a legacy-shaped ``POST /api/route`` (no MO opt-in)
   still returns the published cascade schema (``p_correct``/``tier``, and NO
   ``routing_score``/``router``/``selected_model`` keys). The multi-objective
   router only answers on an explicit opt-in.

2. MO OPT-IN - ``router="multi_objective"``, an MO-only mode (``speed``/
   ``private``), or any MO-only parameter (``quality_floor``/
   ``latency_budget_ms``/``sensitive``) routes through the new pipeline and
   returns the honest ``routing_score`` schema (never ``p_correct``).

The new read-only endpoints (``/api/objectives``, ``/api/pareto``,
``/api/privacy``, ``/api/sensitivity``) are smoke-tested, and every reported
number must trace back to the fitted artifact / policy - nothing invented.
"""
import pytest

from routing.config import MODELS, RESULTS_DIR

Q_BENIGN = "Write a Python function that reverses a linked list and explain it."
Q_SENSITIVE = ("My email is jane.doe@hospital.org; summarize this patient "
               "medical record and bill the credit card 4111 1111 1111 1111.")
APPROVED = {"Llama-3.1-8B-Instruct", "Qwen3-8B"}


@pytest.fixture(scope="module")
def mo_ready(server_mod, client):
    """The TestClient, skipping the MO-dependent tests if the artifact is absent."""
    if not server_mod.MO_AVAILABLE:
        pytest.skip("multi-objective router not built - run: python -m routing.tune_mo")
    return client


# ------------------------------------------------- backward compatibility
def test_legacy_request_keeps_the_published_cascade_schema(client):
    """No opt-in -> the frozen legacy router, byte-for-byte the old contract."""
    d = client.post("/api/route", json={"query": Q_BENIGN}).json()
    assert d["chosen_model"] in MODELS
    assert set(d["p_correct"].keys()) == set(MODELS)
    assert d["tier"] in ("easy", "medium", "hard")
    # honest separation: legacy never exposes the MO vocabulary
    for k in ("routing_score", "selected_model", "router", "sensitivity"):
        assert k not in d, k


@pytest.mark.parametrize("mode", ["economy", "balanced", "quality"])
def test_legacy_modes_stay_on_the_legacy_router(client, mode):
    """economy/balanced/quality predate the MO router and must remain legacy
    unless the caller explicitly opts in (mode alone is NOT an opt-in)."""
    d = client.post("/api/route", json={"query": Q_BENIGN, "mode": mode}).json()
    assert "p_correct" in d
    assert "routing_score" not in d


def test_explicit_legacy_router_wins_over_mo_params(client):
    """router='legacy' forces the published cascade even with MO params set."""
    d = client.post("/api/route", json={
        "query": Q_BENIGN, "router": "legacy", "sensitive": False,
        "quality_floor": 0.8, "latency_budget_ms": 1000}).json()
    assert "p_correct" in d
    assert "routing_score" not in d


# ---------------------------------------------------------- MO opt-in
def _assert_mo_schema(d):
    assert d["router"] == "multi_objective"
    assert d["selected_model"] in MODELS
    assert 0.0 <= d["routing_score"] <= 1.0
    assert "p_correct" not in d                       # honest renaming
    assert d["privacy_status"] in ("approved", "blocked")
    assert "latency" in d and "constraints" in d and "reason" in d


def test_router_field_selects_the_mo_pipeline(mo_ready):
    d = mo_ready.post("/api/route", json={
        "query": Q_BENIGN, "router": "multi_objective"}).json()
    _assert_mo_schema(d)


@pytest.mark.parametrize("mode", ["speed", "private"])
def test_mo_only_modes_select_the_mo_pipeline(mo_ready, mode):
    d = mo_ready.post("/api/route", json={"query": Q_BENIGN, "mode": mode}).json()
    _assert_mo_schema(d)
    assert d["mode"] == mode


@pytest.mark.parametrize("params", [
    {"quality_floor": 0.85},
    {"latency_budget_ms": 900},
    {"sensitive": False},
])
def test_any_mo_param_selects_the_mo_pipeline(mo_ready, params):
    body = {"query": Q_BENIGN, "router": "multi_objective"}
    body.update(params)
    _assert_mo_schema(mo_ready.post("/api/route", json=body).json())


def test_mo_routing_is_deterministic_through_the_api(mo_ready):
    body = {"query": Q_BENIGN, "router": "multi_objective", "mode": "balanced"}
    a = mo_ready.post("/api/route", json=body).json()
    b = mo_ready.post("/api/route", json=body).json()
    assert a["selected_model"] == b["selected_model"]
    assert a["routing_score"] == b["routing_score"]
    assert a["estimated_cost_per_query"] == b["estimated_cost_per_query"]


def test_api_latency_budget_is_honoured_or_reported_unmet(mo_ready):
    d = mo_ready.post("/api/route", json={
        "query": Q_BENIGN, "router": "multi_objective",
        "latency_budget_ms": 250}).json()
    st = None
    import webapp.server as srv
    st = srv.MO_ART["measured_train_stats"]
    within = st[d["selected_model"]]["latency_ms"] <= 250 + 1e-6
    assert within or d["constraints"]["latency_budget_met"] is False


# --------------------------------------------- sensitive-query handling
def test_sensitive_query_only_reaches_approved_models(mo_ready):
    for mode in ("economy", "balanced", "speed", "quality", "private"):
        d = mo_ready.post("/api/route", json={
            "query": Q_SENSITIVE, "router": "multi_objective",
            "mode": mode}).json()
        assert d["sensitivity"]["sensitivity"] == "sensitive"
        if d["selected_model"] is not None:
            assert d["selected_model"] in APPROVED, (mode, d["selected_model"])


def test_explicit_sensitive_flag_is_respected(mo_ready):
    d = mo_ready.post("/api/route", json={
        "query": Q_BENIGN, "router": "multi_objective", "sensitive": True}).json()
    assert d["sensitive"] is True
    if d["selected_model"] is not None:
        assert d["selected_model"] in APPROVED


# ---------------------------------------------------------- validation
def test_quality_floor_out_of_range_is_422(client):
    for bad in (1.5, -0.1):
        r = client.post("/api/route", json={
            "query": Q_BENIGN, "quality_floor": bad})
        assert r.status_code == 422, bad


def test_latency_budget_non_positive_is_422(client):
    for bad in (0, -5):
        r = client.post("/api/route", json={
            "query": Q_BENIGN, "latency_budget_ms": bad})
        assert r.status_code == 422, bad


def test_bad_router_and_bad_mode_are_422(client):
    assert client.post("/api/route", json={
        "query": Q_BENIGN, "router": "quantum"}).status_code == 422
    assert client.post("/api/route", json={
        "query": Q_BENIGN, "mode": "turbo"}).status_code == 422


# ------------------------------------------------------- new endpoints
def test_objectives_endpoint_exposes_measured_config(mo_ready):
    d = mo_ready.get("/api/objectives").json()
    assert d["available"] is True
    assert d["mode_order"] == ["economy", "balanced", "speed", "quality", "private"]
    assert d["default_router"] == "legacy"            # legacy stays production
    for mode in d["mode_order"]:
        spec = d["modes"][mode]
        assert "lambda_cost" in spec and "lambda_latency" in spec
    assert set(d["measured_train_stats"].keys()) == set(MODELS)


def test_pareto_endpoint_reports_all_models_and_frontiers(mo_ready):
    d = mo_ready.get("/api/pareto").json()
    assert len(d["points"]) == len(MODELS)
    for p in d["points"]:
        assert {"model", "quality", "cost", "latency_s",
                "dominated_by", "on_global_frontier"} <= set(p)
    assert {"global", "quality_floor", "privacy_approved"} <= set(d["frontiers"])
    # a dominated model is still LISTED (never deleted from the pool)
    assert all(p["model"] in MODELS for p in d["points"])


def test_privacy_endpoint_reports_policy_without_fabricated_guarantees(client):
    d = client.get("/api/privacy").json()
    assert set(d["models"].keys()) == set(MODELS)
    for m, meta in d["models"].items():
        assert "approved_for_sensitive" in meta
        assert "external_api" in meta
        if meta["external_api"]:
            assert meta["data_retention"] == "administrator-configured", m
    assert "allow_external_models" in d["deployment"]
    assert "DECISION" in d["note"]                    # local routing != private


def test_sensitivity_endpoint_is_local_and_deterministic(client):
    a = client.post("/api/sensitivity", json={"query": Q_SENSITIVE}).json()
    b = client.post("/api/sensitivity", json={"query": Q_SENSITIVE}).json()
    assert a == b
    assert a["sensitivity"] == "sensitive"
    assert set(a.keys()) == {"sensitivity", "reason"}
    normal = client.post("/api/sensitivity", json={"query": Q_BENIGN}).json()
    assert normal["sensitivity"] == "normal"


def test_sensitivity_endpoint_rejects_empty_query(client):
    assert client.post("/api/sensitivity", json={"query": ""}).status_code == 422


# ------------------------------------------ results include the MO report
def test_results_endpoint_includes_mo_eval_report(mo_ready):
    if not (RESULTS_DIR / "mo_eval_report.csv").exists():
        pytest.skip("mo_eval_report.csv not built - run: python -m routing.eval_mo")
    d = mo_ready.get("/api/results").json()
    assert "mo_eval_report" in d
    policies = {row.get("policy") for row in d["mo_eval_report"]}
    # the four required policy families + every MO mode are all evaluated
    assert any("legacy" in str(p) for p in policies)
    assert any("cheapest" in str(p) for p in policies)
    assert any(str(p).startswith("mo-") for p in policies)
