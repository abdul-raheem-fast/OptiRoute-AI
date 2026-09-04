"""Privacy filter + local sensitivity classification (requirements 4 & 5).

Pins the hard rules: the local classifier is deterministic and needs no LLM,
the privacy filter runs BEFORE selection, sensitive queries only ever reach
approved models, and no provider guarantee is fabricated (retention stays
'administrator-configured' unless the deployment asserts otherwise).
"""
import copy

from routing.config import MODELS
from routing.sensitivity import (
    classify_sensitivity, eligibility_mask, load_policy, model_privacy,
)

LOCAL = {"Llama-3.1-8B-Instruct", "Qwen3-8B"}


# ------------------------------------------------------- sensitivity (local)
def test_classify_normal_query_is_normal():
    r = classify_sensitivity("Write a Python function that reverses a string.")
    assert r["sensitivity"] == "normal"
    assert isinstance(r["reason"], str) and r["reason"]


def test_classify_pii_patterns_are_sensitive():
    for text in [
        "My email is jane.doe@hospital.org, please reply",
        "SSN 123-45-6789 on file",
        "card 4111 1111 1111 1111",
        "password = hunter2",
    ]:
        r = classify_sensitivity(text)
        assert r["sensitivity"] == "sensitive", text
        assert r["reason"]


def test_classify_keyword_rule_is_sensitive():
    r = classify_sensitivity("Summarize this patient medical record for billing.")
    assert r["sensitivity"] == "sensitive"
    assert "keyword" in r["reason"].lower() or "pattern" in r["reason"].lower()


def test_classify_is_deterministic_and_local():
    text = "My email is a@b.com and my salary is confidential."
    assert classify_sensitivity(text) == classify_sensitivity(text)
    # The reason names a rule index/keyword - no raw matched content is echoed.
    assert "a@b.com" not in classify_sensitivity(text)["reason"]


def test_classify_returns_the_documented_shape():
    r = classify_sensitivity("hello world")
    assert set(r.keys()) == {"sensitivity", "reason"}
    assert r["sensitivity"] in {"normal", "sensitive"}


# --------------------------------------------------------- eligibility mask
def test_non_sensitive_query_allows_the_whole_pool():
    assert eligibility_mask(MODELS, sensitive=False) == [True] * len(MODELS)


def test_sensitive_query_restricts_to_approved_models():
    mask = eligibility_mask(MODELS, sensitive=True)
    eligible = {m for m, ok in zip(MODELS, mask) if ok}
    approved = set(load_policy()["deployment"]["approved_for_sensitive"])
    assert eligible == approved
    assert eligible <= LOCAL                      # approved set is local-only here


def test_disallow_external_leaves_only_local_models():
    pol = copy.deepcopy(load_policy())
    pol["deployment"]["allow_external_models"] = False
    mask = eligibility_mask(MODELS, sensitive=False, policy=pol)
    assert {m for m, ok in zip(MODELS, mask) if ok} == LOCAL


def test_disallow_sensitive_routing_refuses_everything():
    pol = copy.deepcopy(load_policy())
    pol["deployment"]["allow_sensitive_queries"] = False
    mask = eligibility_mask(MODELS, sensitive=True, policy=pol)
    assert not any(mask)                            # nothing eligible -> blocked


def test_unlisted_model_defaults_to_unapproved_external():
    meta = model_privacy("some-unknown-model")
    assert meta["external_api"] is True
    assert meta["locally_hosted"] is False
    assert meta["approved_for_sensitive"] is False


# ------------------------------------------------- no fabricated guarantees
def test_external_models_do_not_claim_verified_retention():
    pol = load_policy()
    for m, meta in pol["models"].items():
        if meta["external_api"]:
            # Honest default: retention is admin-configured, NOT a vendor promise.
            assert meta["data_retention"] == "administrator-configured", m
        else:
            assert meta["locally_hosted"] is True
    assert pol["_meta"]["provenance"]["data_retention"]


def test_every_pool_model_has_full_privacy_metadata():
    required = {"privacy_level", "external_api", "locally_hosted",
                "data_retention", "approved_for_sensitive", "source"}
    for m in MODELS:
        assert required.issubset(model_privacy(m).keys()), m


# ------------------------------------------- filter runs BEFORE selection
def test_sensitive_query_never_selects_an_unapproved_model(mo_router):
    text = "My email is jane@hospital.org; summarize this patient medical record."
    for mode in ("economy", "balanced", "speed", "quality", "private"):
        d = mo_router.route(text, mode=mode)
        approved = set(load_policy()["deployment"]["approved_for_sensitive"])
        if d["selected_model"] is not None:
            assert d["selected_model"] in approved, (mode, d["selected_model"])
        assert d["sensitivity"]["sensitivity"] == "sensitive"


def test_private_mode_restricts_even_a_benign_query(mo_router):
    d = mo_router.route("Explain the quicksort algorithm and its worst case.",
                        mode="private")
    assert d["selected_model"] in LOCAL
    assert set(d["eligible_models"]) <= LOCAL


def test_blocked_when_policy_refuses_sensitive(mo_router, monkeypatch):
    """allow_sensitive_queries=false + a sensitive query -> nothing is routed."""
    pol = copy.deepcopy(load_policy())
    pol["deployment"]["allow_sensitive_queries"] = False
    import routing.sensitivity as sens
    # eligibility_mask resolves load_policy() from the module globals at call
    # time, so patching it flips the deployment rule for this test only.
    monkeypatch.setattr(sens, "load_policy", lambda: pol)
    from webapp.mo_router import MoRouter
    r = MoRouter(core=mo_router.core)
    d = r.route("My SSN is 123-45-6789 and my email is a@b.com", mode="balanced")
    assert d["selected_model"] is None
    assert d["privacy_status"] == "blocked"
