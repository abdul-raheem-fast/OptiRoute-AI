"""Single source of truth for the multi-objective routing configuration.

Objective (per eligible model m, per query):

    utility(m) = calibrated_quality(m)
                 - lambda_cost    * norm_cost(m)
                 - lambda_latency * norm_latency(m)

with ``norm_*`` = min-max normalisation of the MEASURED train-split statistics
over the whole pool (so a weight of 1.0 means "one full pool-wide cost spread
is worth one full quality point").  Privacy and the latency budget are HARD
constraints (a model outside the policy, or slower than the budget, is removed
before the utility is evaluated, because a soft penalty could still route a
sensitive query - or miss a deadline - on an inadmissible model).

Two distinct quality constraints (they are NOT the same knob):
  * POLICY floor (``quality_floor_rule``) - the accuracy the whole mode must
    keep, verified on the validation split (``meets_floor``).  This is the
    project's published QUALITY_FLOOR semantic: "at least 90% of the
    always-strongest policy accuracy".  It shapes the mode via the utility
    weights, it is NOT a per-query gate.
  * PER-QUERY floor (the API ``quality_floor`` / UI slider) - an optional HARD
    minimum calibrated quality for the single chosen model, applied in
    :func:`routing.mo_core.select` only when the caller supplies it.  Off by
    default so the modes below can span the real cost/quality spectrum.

Weight semantics (why these numbers, not arbitrary ones):
  * lambda_cost = 1.0  -> the entire pool cost spread ($0.000013..$0.0829/query)
    trades one-for-one against a full quality point: cost is the objective.
  * lambda_cost = 0.5  -> cost matters, but a 0.5 quality point gain still
    justifies paying the whole pool spread: the balanced compromise.
  * lambda_latency = 1.0 -> the entire pool latency spread trades one-for-one
    against quality: latency is the objective (Speed mode, plus a hard budget).
  * lambda_latency = 0.1 -> latency is a TIEBREAKER outside Speed mode.  The
    measured pool latency spread is inflated by a single slow outlier (Qwen3-8B
    ~3.7s vs gemini-2.5-flash ~0.2s), so 0.1 caps the whole spread at ~10
    accuracy points: latency only decides when two models are within ~10 pts of
    calibrated quality.  A larger weight let one model's slowness override a
    large correctness gap (observed: it made a sensitive query prefer a
    37%-accuracy model over a 77%-accuracy one purely for speed).
  * 0.0 -> the dimension is reported but not optimised (quality mode).

Hard-constraint rules reference MEASURED quantities only:
  * ``floor90``    - 90% of the always-strongest policy accuracy (the project's
                     published QUALITY_FLOOR, routing.config); POLICY-level.
  * ``flagship_latency`` - the measured average latency of the strongest model
                     on the train split, i.e. "no slower than always-GPT-5".
                     This is a measured default, not an invented target, stays
                     overridable per request (latency_budget_ms) and is visible
                     in the UI.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModeSpec:
    key: str
    label: str
    description: str
    lambda_cost: float
    lambda_latency: float
    quality_floor_rule: str | None      # POLICY floor verified on val:
                                        # "floor90" | "strongest" | None
    latency_budget_rule: str | None     # HARD per-query budget:
                                        # "flagship_latency" | None
    privacy_restricted: bool = False    # only policy-approved models eligible
    notes: str = ""


MODES: dict[str, ModeSpec] = {
    m.key: m for m in (
        ModeSpec(
            "economy", "Economy",
            "Maximum savings: cost is the objective; latency is a tiebreaker and "
            "quality enters through the calibrated score. Targets (and is "
            "verified against) the 90% policy quality floor.",
            lambda_cost=1.0, lambda_latency=0.1,
            quality_floor_rule="floor90", latency_budget_rule=None,
            notes="High lambda_cost drives the cheap+fast models; the soft "
                  "quality term still rejects models too weak to be worth free."),
        ModeSpec(
            "balanced", "Balanced",
            "Quality, cost and latency weighted jointly - the direct "
            "multi-objective successor of the legacy policy. Targets the 90% "
            "policy quality floor.",
            lambda_cost=0.5, lambda_latency=0.1,
            quality_floor_rule="floor90", latency_budget_rule=None,
            notes="lambda_latency 0.1: latency breaks near-ties but does not "
                  "override correctness (see module docstring)."),
        ModeSpec(
            "speed", "Speed",
            "Latency-budgeted routing: only models at or under the measured "
            "always-strongest average latency compete (HARD budget), then "
            "latency is the objective inside that set.",
            lambda_cost=0.25, lambda_latency=1.0,
            quality_floor_rule="floor90", latency_budget_rule="flagship_latency"),
        ModeSpec(
            "quality", "Quality",
            "Predicted quality only: cost and latency are reported, not "
            "optimised; the highest-calibrated-quality eligible model wins.",
            lambda_cost=0.0, lambda_latency=0.0,
            quality_floor_rule=None, latency_budget_rule=None),
        ModeSpec(
            "private", "Private",
            "Hard privacy constraint: only deployment-approved (locally hosted) "
            "models are eligible, then quality+cost optimised inside that set "
            "with latency as a tiebreaker.",
            lambda_cost=0.5, lambda_latency=0.1,
            quality_floor_rule=None, latency_budget_rule=None,
            privacy_restricted=True,
            notes="No policy floor: the approved set is fixed by the deployment, "
                  "so quality is reported honestly even when it is lower."),
    )
}

MODE_ORDER = ["economy", "balanced", "speed", "quality", "private"]

# Which router answers /api/route by default. Decided from validation-split
# evidence in routing/eval_mo.py; the legacy cascade keeps the published,
# test-verified headline numbers, so it stays the default unless the
# multi-objective router beats it on validation.
DEFAULT_ROUTER = "legacy"

# Utility normalisation uses the pool-wide measured spread of these stats.
NORM_DIMS = ("cost", "latency")

__all__ = ["MODES", "MODE_ORDER", "ModeSpec", "DEFAULT_ROUTER", "NORM_DIMS"]
