"""Pure multi-objective selection logic (no I/O, no featurization).

Shared by :mod:`routing.tune_mo` (validation), :mod:`routing.eval_mo` (sealed
test) and :mod:`webapp.mo_router` (live ``/api/route``) so that all three answer
identically for identical inputs.  Every number that enters the decision comes
from MEASURED train-split statistics supplied by the caller - nothing here
invents a cost, a latency or a quality target.

Decision pipeline (mirrors the proposal's required architecture)::

    eligible set (privacy HARD filter, decided by the caller)
      -> latency-budget HARD filter (speed modes)
      -> quality-floor HARD filter (per-query calibrated quality)
      -> utility = calibrated_quality
                   - lambda_cost    * minmax(cost)
                   - lambda_latency * minmax(latency)
      -> argmax utility, else fallback to the strongest eligible model

Quality and privacy are HARD constraints (applied before the utility), because a
soft penalty could still spend money - or route a sensitive query - to an
inadmissible model.  Cost and latency are SOFT (weighted) inside the admissible
set.  ``minmax`` uses the pool-wide measured spread, so a weight of 1.0 means
"one full pool-wide cost (latency) spread trades against one quality point".
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def platt(z, a: float, b: float):
    """Per-head Platt calibration: ``sigmoid(a * logit + b)``."""
    return 1.0 / (1.0 + np.exp(-(a * np.asarray(z, dtype=float) + b)))


def minmax(v, lo: float, hi: float):
    """Min-max normalise against a FIXED pool reference (hi>lo)."""
    v = np.asarray(v, dtype=float)
    if hi <= lo:
        return np.zeros_like(v)
    return (v - lo) / (hi - lo)


@dataclass(frozen=True)
class Norm:
    """Pool-wide measured reference ranges used for utility normalisation."""
    cost_min: float
    cost_max: float
    latency_min: float
    latency_max: float

    @classmethod
    def from_stats(cls, cost, latency_s) -> "Norm":
        cost = np.asarray(cost, dtype=float)
        lat = np.asarray(latency_s, dtype=float)
        return cls(float(cost.min()), float(cost.max()),
                   float(lat.min()), float(lat.max()))


@dataclass(frozen=True)
class Policy:
    """A fully-resolved routing policy for one request/mode.

    ``elig`` is the HARD privacy mask (bool per model) decided by the caller
    from the deployment policy + query sensitivity; this module never guesses
    privacy.  ``quality_floor`` and ``latency_budget_s`` are HARD filters
    (``None`` disables).  ``lambda_cost`` / ``lambda_latency`` are the SOFT
    utility weights.
    """
    key: str
    elig: np.ndarray            # bool[M]
    lam_cost: float
    lam_latency: float
    quality_floor: float | None
    latency_budget_s: float | None


def select(p_cal, acc, cost, latency_s, policy: Policy, norm: Norm) -> dict:
    """Choose one model for a single query under a resolved :class:`Policy`.

    Parameters are per-model arrays (len M) in ``routing.config.MODELS`` order:
      * ``p_cal``      - calibrated P(correct) for THIS query
      * ``acc``        - measured train-split accuracy (defines "strongest")
      * ``cost``       - measured train-split avg cost/query
      * ``latency_s``  - measured train-split avg latency (seconds)
      * ``norm``       - the FIXED pool-wide measured reference ranges, so the
                         utility weights keep one meaning across modes/queries.

    Returns a dict with the chosen index and everything needed to explain the
    decision.  ``chosen is None`` only when the privacy filter left nothing
    eligible (the caller decides how to surface that).
    """
    p_cal = np.asarray(p_cal, dtype=float)
    acc = np.asarray(acc, dtype=float)
    cost = np.asarray(cost, dtype=float)
    lat = np.asarray(latency_s, dtype=float)
    m = len(p_cal)
    elig = np.asarray(policy.elig, dtype=bool)

    out = {
        "chosen": None, "is_fallback": False, "budget_met": None,
        "utility": np.zeros(m), "admissible": np.zeros(m, dtype=bool),
        "eligible": elig.copy(), "reason_code": "",
    }
    idx = np.where(elig)[0]
    if idx.size == 0:
        out["reason_code"] = "no_eligible_model"
        return out

    # ---- HARD filter 1: latency budget (speed modes) ----------------------
    if policy.latency_budget_s is not None:
        within = idx[lat[idx] <= policy.latency_budget_s]
        budget_met = within.size > 0
        # If nothing meets the budget, degrade gracefully to the single fastest
        # eligible model rather than failing (fancy-index -> 1-D array of len 1).
        fastest = idx[np.array([int(np.argmin(lat[idx]))])]
        cand = within if budget_met else fastest
        cand = np.atleast_1d(cand).ravel()
        out["budget_met"] = bool(budget_met)
        if not budget_met:
            out["reason_code"] = "latency_budget_unmet_used_fastest"
    else:
        cand = idx

    # ---- HARD filter 2: per-query quality floor ---------------------------
    strongest_elig = int(cand[np.argmax(acc[cand])])
    if policy.quality_floor is not None:
        adm = cand[p_cal[cand] >= policy.quality_floor]
        if adm.size > 0:
            final = adm
        else:
            # Nothing clears the floor for this query -> escalate to the
            # strongest eligible model (mirrors the legacy fallback-to-gpt-5).
            final = np.array([strongest_elig])
            out["is_fallback"] = True
            if not out["reason_code"]:
                out["reason_code"] = "quality_floor_escalated_to_strongest"
    else:
        final = cand

    out["admissible"][final] = True

    # ---- SOFT objective: utility over the admissible set ------------------
    nc = minmax(cost[final], norm.cost_min, norm.cost_max)
    nl = minmax(lat[final], norm.latency_min, norm.latency_max)
    util = p_cal[final] - policy.lam_cost * nc - policy.lam_latency * nl
    out["utility"][final] = util
    chosen = int(final[int(np.argmax(util))])
    out["chosen"] = chosen
    if not out["reason_code"]:
        out["reason_code"] = "utility_argmax"
    out["strongest_elig"] = strongest_elig
    return out


__all__ = ["platt", "minmax", "Norm", "Policy", "select"]
