"""Live multi-objective router for ``/api/route`` (experimental/advanced path).

Wraps the frozen learned heads (:class:`webapp.router_core.RouterCore`) with the
fitted multi-objective artifact (``routing/models/mo_objectives.json``): per-head
Platt calibration, measured cost/latency/quality, the privacy filter, the latency
budget and the utility objective in :mod:`routing.mo_core`.  The routing decision
itself needs NO LLM call - it is pure local featurization + arithmetic.

Pipeline (mirrors the proposal)::

    query -> features -> privacy filter -> Pareto/eligibility
          -> calibrated quality -> cost+latency+quality utility -> model

Honesty notes baked into the response:
  * the score is CALIBRATED (Platt, fit on train, verified on val) and is
    reported as ``routing_score`` / ``calibrated_quality`` - never as a literal
    ``p_correct`` probability claim;
  * ``estimated_*`` cost/latency are the chosen model's MEASURED benchmark
    averages - estimates for an arbitrary query, labelled as such;
  * latency is split into router overhead (measured live), model inference
    (measured benchmark average) and end-to-end (their sum);
  * "local routing" means the DECISION needs no extra LLM call - it does NOT
    mean the selected model is private. Privacy comes only from the deployment
    policy filter.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from routing.config import MODELS, ROOT, STRONGEST
from routing.learned_router import sigmoid
from routing.mo_core import Norm, Policy, platt, select
from routing.sensitivity import classify_sensitivity, eligibility_mask, load_policy

ARTIFACT_PATH = ROOT / "routing" / "models" / "mo_objectives.json"
SI = MODELS.index(STRONGEST)

_PRIVACY_NOTE = (
    "Local routing means the routing DECISION needs no extra LLM call; it does "
    "NOT mean the selected model is private. Privacy is enforced only by the "
    "deployment policy filter."
)


class MoRouter:
    """Multi-objective router. Deterministic: same inputs -> same decision."""

    def __init__(self, core=None, artifact_path: Path | None = None):
        if core is None:
            from webapp.router_core import RouterCore
            core = RouterCore()
        self.core = core
        path = Path(artifact_path) if artifact_path else ARTIFACT_PATH
        if not path.exists():
            raise FileNotFoundError(
                f"{path} missing - run: python -m routing.tune_mo")
        with open(path, encoding="utf-8") as f:
            self.art = json.load(f)

        st = self.art["measured_train_stats"]
        self.acc = np.array([st[m]["accuracy"] for m in MODELS], dtype=float)
        self.cost = np.array([st[m]["cost"] for m in MODELS], dtype=float)
        self.lat = np.array([st[m]["latency_s"] for m in MODELS], dtype=float)
        cal = self.art["calibration"]
        self.cal_a = np.array([cal[m]["a"] for m in MODELS], dtype=float)
        self.cal_b = np.array([cal[m]["b"] for m in MODELS], dtype=float)
        nrm = self.art["normalization"]
        self.norm = Norm(nrm["cost_min"], nrm["cost_max"],
                         nrm["latency_min"], nrm["latency_max"])
        self.modes = self.art["modes"]
        self.frontiers = self.art["frontiers"]
        self.default_mode = "balanced"

        pol = load_policy()
        self.approved = set(pol.get("deployment", {}).get("approved_for_sensitive", []))
        self._approved_mask = np.array([m in self.approved for m in MODELS])
        self._all_mask = np.ones(len(MODELS), dtype=bool)

    # ------------------------------------------------------------- scoring
    def _calibrated(self, query: str, cls: str):
        """Raw head scores + Platt-calibrated quality for one query."""
        x = self.core.featurize(query, cls)
        z = x @ self.core.W + self.core.b
        raw = sigmoid(z)
        p_cal = platt(z, self.cal_a, self.cal_b)
        return raw, p_cal

    # ---------------------------------------------------------------- route
    def route(self, query: str, query_class: str | None = None,
              mode: str | None = None, quality_floor: float | None = None,
              latency_budget_ms: float | None = None,
              sensitive: bool | None = None) -> dict:
        t0 = time.perf_counter()
        mode = mode if mode in self.modes else self.default_mode
        spec = self.modes[mode]
        cls = query_class if query_class in self.core.classes \
            else self.core.guess_class(query)

        raw, p_cal = self._calibrated(query, cls)

        # ---- 1. PRIVACY FILTER (before any selection) --------------------
        sens = classify_sensitivity(query)          # local, deterministic
        is_sensitive = (sens["sensitivity"] == "sensitive") if sensitive is None \
            else bool(sensitive)
        elig = np.array(eligibility_mask(MODELS, is_sensitive), dtype=bool)
        if spec.get("privacy_restricted"):
            elig = elig & self._approved_mask
        privacy_blocked = not elig.any()

        # ---- 2. resolve HARD constraints ---------------------------------
        lb_ms = latency_budget_ms if latency_budget_ms is not None \
            else spec.get("latency_budget_ms")
        lb_s = (float(lb_ms) / 1000.0) if lb_ms is not None else None
        qf = float(quality_floor) if quality_floor is not None else None

        if privacy_blocked:
            overhead = (time.perf_counter() - t0) * 1000
            return self._blocked(mode, spec, cls, sens, is_sensitive,
                                 p_cal, overhead)

        # ---- 3. utility selection ----------------------------------------
        policy = Policy(mode, elig, float(spec["lambda_cost"]),
                        float(spec["lambda_latency"]), qf, lb_s)
        res = select(p_cal, self.acc, self.cost, self.lat, policy, self.norm)
        overhead = (time.perf_counter() - t0) * 1000
        chosen = res["chosen"]

        model_inf_ms = float(self.lat[chosen]) * 1000.0
        return self._explain(query, mode, spec, cls, sens, is_sensitive, elig,
                             raw, p_cal, res, chosen, qf, lb_ms,
                             overhead, model_inf_ms)

    # ------------------------------------------------------------ responses
    def _blocked(self, mode, spec, cls, sens, is_sensitive, p_cal, overhead):
        return {
            "router": "multi_objective",
            "selected_model": None,
            "chosen_model": None,
            "mode": mode,
            "mode_label": spec["label"],
            "query_class": cls,
            "routing_score": None,
            "privacy_status": "blocked",
            "sensitivity": sens,
            "sensitive": is_sensitive,
            "reason": ("No model is eligible: the query is sensitive (or the "
                       "deployment forbids the required providers) and the "
                       "privacy policy approves no model for it. Nothing was "
                       "routed. " + _PRIVACY_NOTE),
            "estimated_cost_per_query": 0.0,
            "est_cost_per_query": 0.0,
            "strongest_cost_per_query": round(float(self.cost[SI]), 6),
            "is_fallback": False,
            "tier": None,
            "latency": {"router_overhead_ms": round(overhead, 3),
                        "model_inference_ms": 0.0,
                        "end_to_end_ms": round(overhead, 3)},
            "calibrated_quality": {m: round(float(p), 4)
                                   for m, p in zip(MODELS, p_cal)},
            "eligible_models": [],
        }

    def _explain(self, query, mode, spec, cls, sens, is_sensitive, elig,
                 raw, p_cal, res, chosen, qf, lb_ms, overhead, model_inf_ms):
        code = res["reason_code"]
        name = MODELS[chosen]
        strong_elig = int(res.get("strongest_elig", chosen))
        is_fallback = bool(res["is_fallback"])

        # ---- human-readable reason --------------------------------------
        if code == "quality_floor_escalated_to_strongest":
            reason = (f"No eligible model reached the per-query quality floor "
                      f"({qf:.2f}); escalated to the strongest eligible model "
                      f"({name}) - quality is the binding constraint.")
        elif code == "latency_budget_unmet_used_fastest":
            reason = (f"No eligible model met the {lb_ms:.0f} ms latency budget; "
                      f"used the fastest eligible model ({name}).")
        else:
            reason = (f"Best quality/cost/latency utility among eligible models "
                      f"under the {spec['label']} objective.")

        util = res["utility"]
        strongest_cost = float(self.cost[SI])
        est_cost = float(self.cost[chosen])
        frontier_hits = [k for k, v in self.frontiers.items() if name in v]

        per_model = [{
            "model": m,
            "routing_score": round(float(p_cal[i]), 4),
            "raw_score": round(float(raw[i]), 4),
            "utility": round(float(util[i]), 4),
            "eligible": bool(elig[i]),
            "admissible": bool(res["admissible"][i]),
            "on_global_frontier": m in self.frontiers["global"],
            "measured_accuracy_pct": round(float(self.acc[i]) * 100, 2),
            "measured_cost_per_query": round(float(self.cost[i]), 6),
            "measured_latency_ms": round(float(self.lat[i]) * 1000, 1),
        } for i, m in enumerate(MODELS)]

        return {
            "router": "multi_objective",
            "selected_model": name,
            "chosen_model": name,                 # legacy-compatible alias
            "chosen_index": chosen,
            "mode": mode,
            "mode_label": spec["label"],
            "query_class": cls,
            "is_fallback": is_fallback,
            # CALIBRATED quality (Platt, fit on train, verified on val). This
            # is the honest successor of the legacy `p_correct`.
            "routing_score": round(float(p_cal[chosen]), 4),
            "predicted_quality": round(float(p_cal[chosen]), 4),
            "estimated_cost_per_query": round(est_cost, 6),
            "est_cost_per_query": round(est_cost, 6),          # legacy alias
            "strongest_cost_per_query": round(strongest_cost, 6),
            "estimated_latency_ms": round(model_inf_ms, 1),
            "estimated_latency_s": round(float(self.lat[chosen]), 3),
            "latency": {
                "router_overhead_ms": round(overhead, 3),
                "model_inference_ms": round(model_inf_ms, 1),
                "end_to_end_ms": round(overhead + model_inf_ms, 1),
                "note": ("router_overhead measured live; model_inference is the "
                         "chosen model's MEASURED benchmark average (an estimate "
                         "for an arbitrary query); end_to_end is their sum."),
            },
            "privacy_status": "approved",
            "sensitivity": sens,
            "sensitive": is_sensitive,
            "privacy_note": _PRIVACY_NOTE,
            "constraints": {
                "quality_floor": qf,
                "latency_budget_ms": (round(float(lb_ms), 1) if lb_ms is not None else None),
                "latency_budget_met": res.get("budget_met"),
                "privacy_restricted": bool(spec.get("privacy_restricted")),
                "lambda_cost": float(spec["lambda_cost"]),
                "lambda_latency": float(spec["lambda_latency"]),
            },
            "reason": reason,
            "reason_code": code,
            "pareto": {
                "on_frontier": frontier_hits,
                "global_frontier": self.frontiers["global"],
                "is_strongest_eligible": chosen == strong_elig,
            },
            "why_not_strongest": {
                "strongest_model": STRONGEST,
                "delta_quality_pts": round(float(p_cal[SI] - p_cal[chosen]) * 100, 2),
                "delta_cost_per_query": round(strongest_cost - est_cost, 6),
                "verdict": ("the strongest eligible model is the route"
                            if chosen == strong_elig else
                            f"+{float(p_cal[SI] - p_cal[chosen]) * 100:.1f} pts "
                            f"calibrated quality for +${strongest_cost - est_cost:.5f}"
                            f"/query does not pay under {spec['label']}"),
            },
            "est_saving_pct": round((1 - est_cost / strongest_cost) * 100, 1)
                              if strongest_cost > 0 else 0.0,
            "eligible_models": [MODELS[i] for i in np.where(elig)[0]],
            "model_scores": per_model,
            "calibrated_quality": {m: round(float(p), 4)
                                   for m, p in zip(MODELS, p_cal)},
        }


_router: MoRouter | None = None


def get_router(core=None) -> MoRouter:
    """Process-wide singleton (mirrors webapp.server's `core = RouterCore()`)."""
    global _router
    if _router is None:
        _router = MoRouter(core=core)
    return _router


__all__ = ["MoRouter", "get_router", "ARTIFACT_PATH"]
