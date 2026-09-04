"""Deterministic, local query-sensitivity classification.

Deliberately boring on purpose: the classifier is a set of compiled regular
expressions plus a keyword list, both loaded from webapp/privacy_policy.json,
evaluated in-process.  No query is ever sent to another model - external or
local - merely to decide whether it is sensitive, and the router does not
persist raw query text.

Returns ``{"sensitivity": "normal" | "sensitive", "reason": ...}`` where the
reason names the rule that fired (pattern index or keyword) so the decision is
auditable without exposing the matched content.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

POLICY_PATH = Path(__file__).resolve().parent.parent / "webapp" / "privacy_policy.json"


@lru_cache(maxsize=1)
def load_policy() -> dict:
    with open(POLICY_PATH, encoding="utf-8") as f:
        return json.load(f)


def reload_policy() -> dict:
    """Drop the cache (admins editing privacy_policy.json at runtime)."""
    load_policy.cache_clear()
    return load_policy()


@lru_cache(maxsize=1)
def _compiled() -> tuple[list[re.Pattern], tuple[str, ...]]:
    sens = load_policy().get("sensitivity", {})
    pats = [re.compile(p, re.IGNORECASE) for p in sens.get("patterns", [])]
    return pats, tuple(k.lower() for k in sens.get("keywords", ()))


def classify_sensitivity(text: str) -> dict:
    """Local, deterministic sensitivity decision for one query string."""
    pats, keywords = _compiled()
    s = text or ""
    for i, pat in enumerate(pats):
        if pat.search(s):
            return {"sensitivity": "sensitive",
                    "reason": f"local pattern #{i} matched (PII/credential shape)"}
    low = s.lower()
    for kw in keywords:
        if kw in low:
            return {"sensitivity": "sensitive",
                    "reason": f"local keyword rule matched: '{kw}'"}
    return {"sensitivity": "normal",
            "reason": "no local sensitivity rule matched"}


def model_privacy(model: str, policy: dict | None = None) -> dict:
    """Privacy metadata for one model from the deployment policy file."""
    pol = policy if policy is not None else load_policy()
    models = pol.get("models", {})
    return models.get(model, {"privacy_level": "external-api",
                              "external_api": True,
                              "locally_hosted": False,
                              "data_retention": "administrator-configured",
                              "approved_for_sensitive": False,
                              "source": "not listed in privacy_policy.json"})


def eligibility_mask(models: tuple[str, ...] | list[str],
                     sensitive: bool,
                     policy: dict | None = None) -> list[bool]:
    """Hard privacy filter, evaluated BEFORE any model selection.

    Rules, in order:
      * sensitive query + deployment forbids sensitive routing -> nothing eligible
      * sensitive query -> only ``approved_for_sensitive`` models
      * deployment forbids external models -> only locally hosted models
    """
    pol = policy if policy is not None else load_policy()
    dep = pol.get("deployment", {})
    allow_external = bool(dep.get("allow_external_models", True))
    allow_sensitive = bool(dep.get("allow_sensitive_queries", True))
    approved = set(dep.get("approved_for_sensitive", []))
    out = []
    for m in models:
        meta = model_privacy(m, pol)
        if sensitive:
            ok = allow_sensitive and (m in approved or meta["approved_for_sensitive"])
        else:
            ok = True
        if ok and not allow_external and meta.get("external_api", True):
            ok = False
        out.append(bool(ok))
    return out
