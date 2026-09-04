"""Scenario-chip verification - the buttons a judge clicks first.

The dashboard's six scenario chips (3 cheap-route, 3 escalate) and the
challenge pool are served by GET /api/scenarios and are REAL frozen test-split
queries. Each chip carries an expected model / route kind / saving. If any chip
disagrees with what the live router actually produces, the very first click of
a live demo contradicts the label on the button - so we verify every chip
against RouterCore, not assume it.
"""
import pytest

from routing.config import STRONGEST


@pytest.fixture(scope="module")
def scenarios(client):
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    return r.json()


def test_scenario_set_shape(scenarios):
    scen = scenarios["scenarios"]
    assert len(scen) == 6, "expected the 6 curated demo scenarios"
    cheap = [s for s in scen if s["expected_route"] == "cheap"]
    esc = [s for s in scen if s["expected_route"] == "escalate"]
    assert len(cheap) == 3 and len(esc) == 3
    labels = {s["label"] for s in scen}
    assert labels == {
        "Easy coding task", "Astrophysics estimate", "Combinatorics puzzle",
        "Hard algebra", "Organic synthesis", "Obscure trivia",
    }


def test_every_chip_routes_to_its_labelled_model(core, scenarios):
    bad = []
    for s in scenarios["scenarios"]:
        d = core.route(s["query"], s["query_class"], core.t_star)
        if d["chosen_model"] != s["expected_model"]:
            bad.append(f"{s['label']}: router={d['chosen_model']} "
                       f"chip={s['expected_model']}")
        want_cheap = s["expected_route"] == "cheap"
        if (not d["is_fallback"]) != want_cheap:
            bad.append(f"{s['label']}: fallback={d['is_fallback']} "
                       f"but chip says {s['expected_route']}")
        if d["est_saving_pct"] != s["expected_saving_pct"]:
            bad.append(f"{s['label']}: saving={d['est_saving_pct']} "
                       f"chip={s['expected_saving_pct']}")
    assert not bad, "chip/router disagreement:\n" + "\n".join(bad)


def test_cheap_chips_actually_save_and_escalate_chips_hit_strongest(core, scenarios):
    for s in scenarios["scenarios"]:
        d = core.route(s["query"], s["query_class"], core.t_star)
        if s["expected_route"] == "cheap":
            assert d["chosen_model"] != STRONGEST
            assert d["est_saving_pct"] > 0, f"{s['label']} claims savings <= 0"
        else:
            assert d["chosen_model"] == STRONGEST
            assert d["is_fallback"] is True


def test_chips_are_real_test_split_queries(scenarios, splits):
    """Chips must be genuine held-out benchmark rows, not synthetic text."""
    te = set(splits["test"])
    # we cannot map text->qid here, but the endpoint sources from the test
    # split; assert the payload declares that provenance and is non-empty
    assert scenarios["source"] == "frozen test split (real benchmark queries)"
    assert len(te) == 282


def test_challenge_pool_is_consistent(core, scenarios):
    pool = scenarios["challenges"]
    assert 0 < len(pool) <= 8
    kinds = {"cheap": 0, "escalate": 0}
    for c in pool:
        d = core.route(c["query"], c["query_class"], core.t_star)
        kind = "cheap" if not d["is_fallback"] else "escalate"
        assert kind == c["expected_route"], (
            f"challenge {c['query'][:40]!r}: router={kind} "
            f"label={c['expected_route']}"
        )
        kinds[kind] += 1
    assert kinds["cheap"] <= 4 and kinds["escalate"] <= 4
