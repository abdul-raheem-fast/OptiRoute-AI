"""Mode and threshold logic - the three routing policies are threshold
presets over one router, so we verify the EFFECTIVE gate actually used in
routing, not just the label shown in the UI.
"""
import pytest

from webapp.export_weights import MODE_SPECS

QUERY = "Summarize the causes of the French Revolution in three bullets."


def test_mode_thresholds_match_export_specs_exactly(core, server_mod):
    """No drift between export_weights.MODE_SPECS and the runtime MODE_T."""
    spec = {key: t for key, _label, t in MODE_SPECS}
    assert spec["economy"] == pytest.approx(0.80)
    assert spec["quality"] == pytest.approx(0.99)
    assert spec["balanced"] is None  # resolved to t_star at export time

    assert server_mod.MODE_T["economy"] == pytest.approx(spec["economy"])
    assert server_mod.MODE_T["quality"] == pytest.approx(spec["quality"])
    # balanced resolves to the val-tuned t_star, rounded for display
    assert server_mod.MODE_T["balanced"] == pytest.approx(round(core.t_star, 2))
    assert server_mod.MODE_T["balanced"] == pytest.approx(0.95)


def test_mode_thresholds_are_distinct_and_ordered(server_mod):
    t = server_mod.MODE_T
    assert t["economy"] < t["balanced"] < t["quality"]


@pytest.mark.parametrize("mode,expected", [
    ("economy", 0.80),
    ("balanced", 0.95),
    ("quality", 0.99),
])
def test_mode_sets_the_effective_routing_threshold(client, mode, expected):
    """The response echoes the gate actually used; confirm it per mode."""
    r = client.post("/api/route", json={"query": QUERY, "mode": mode})
    assert r.status_code == 200
    body = r.json()
    assert body["threshold"] == pytest.approx(expected), (
        f"mode={mode} routed with t={body['threshold']}, expected {expected}"
    )


def test_default_mode_is_balanced(client, core):
    r = client.post("/api/route", json={"query": QUERY})
    assert r.status_code == 200
    assert r.json()["threshold"] == pytest.approx(0.95)


def test_explicit_threshold_overrides_mode(client):
    """mode=quality (t=0.99) + explicit threshold=0.80 -> 0.80 must win."""
    r = client.post("/api/route",
                    json={"query": QUERY, "mode": "quality", "threshold": 0.80})
    assert r.status_code == 200
    assert r.json()["threshold"] == pytest.approx(0.80)

    # threshold alone (no mode)
    r2 = client.post("/api/route", json={"query": QUERY, "threshold": 0.85})
    assert r2.status_code == 200
    assert r2.json()["threshold"] == pytest.approx(0.85)


def test_threshold_changes_the_decision_monotonically(core):
    """A higher gate must never route CHEAPER than a lower gate: the chosen
    index is non-decreasing in t (cascade walks cheap->strong)."""
    idx_prev = -1
    for t in (0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.99):
        d = core.route(QUERY, "General Knowledge", t)
        assert d["chosen_index"] >= idx_prev, f"t={t} routed cheaper than a lower t"
        idx_prev = d["chosen_index"]


def test_mode_presets_carry_honest_validation_metrics(core):
    """Each preset quotes a measured val-split number and a floor verdict."""
    keys = [p["key"] for p in core.mode_presets]
    assert keys == ["economy", "balanced", "quality"]
    for p in core.mode_presets:
        assert 0.0 < p["val_accuracy_pct"] <= 100.0
        assert p["val_avg_cost_per_query"] > 0
        assert isinstance(p["meets_floor"], bool)
    # balanced is the headline policy and must clear the quality floor
    bal = next(p for p in core.mode_presets if p["key"] == "balanced")
    assert bal["meets_floor"] is True
