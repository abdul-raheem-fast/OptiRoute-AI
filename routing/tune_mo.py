"""Fit + verify the multi-objective routing artifact (``mo_objectives.json``).

Leakage hygiene (the whole point of this script):
  * the frozen heads (``router_weights.npz``) are NEVER retrained here;
  * measured per-model statistics (accuracy / cost / latency) come from the
    TRAIN split only;
  * per-head Platt calibration is FIT on TRAIN;
  * the five routing modes are VERIFIED (not tuned) on the VALIDATION split;
  * the sealed TEST split is never touched - ``routing.eval_mo`` reports it once.

Everything numeric that the live router needs is written to
``routing/models/mo_objectives.json`` so inference is a pure lookup + the shared
:func:`routing.mo_core.select` - no re-measurement, no drift.

Run after any matrix/splits/weights rebuild:  ``python -m routing.tune_mo``
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from routing.config import MODELS, OUT_DIR, QUALITY_FLOOR, ROOT, STRONGEST
from routing.learned_router import make_X, route_cascade, sigmoid
from routing.mo_core import Norm, Policy, platt, select
from routing.objectives import DEFAULT_ROUTER, MODES, MODE_ORDER
from routing.pareto import model_frontier
from routing.sensitivity import load_policy
from routing.splits import load_splits

WEIGHTS_PATH = ROOT / "routing" / "models" / "router_weights.npz"
ARTIFACT_PATH = ROOT / "routing" / "models" / "mo_objectives.json"
SI = MODELS.index(STRONGEST)          # strongest-model column index


# ------------------------------------------------------------- calibration
def fit_platt(z, y, l2: float = 1e-2, iters: int = 100):
    """Platt scaling ``sigmoid(a*z + b)`` by penalised Newton (damped + L2).

    L2 is centred on the identity map (a=1, b=0) so near-separable heads cannot
    diverge; backtracking guarantees monotone descent on the penalised NLL.
    """
    z = np.asarray(z, dtype=float)
    y = np.asarray(y, dtype=float)
    a, b = 1.0, 0.0

    def obj(aa, bb):
        s = np.clip(1.0 / (1.0 + np.exp(-(aa * z + bb))), 1e-9, 1 - 1e-9)
        nll = float(np.mean(-(y * np.log(s) + (1 - y) * np.log(1 - s))))
        return nll + 0.5 * l2 * ((aa - 1) ** 2 + bb ** 2)

    for _ in range(iters):
        s = np.clip(1.0 / (1.0 + np.exp(-(a * z + b))), 1e-9, 1 - 1e-9)
        r = s - y
        ga = float(np.mean(r * z)) + l2 * (a - 1)
        gb = float(np.mean(r)) + l2 * b
        w = s * (1 - s)
        haa = float(np.mean(w * z * z)) + l2
        hab = float(np.mean(w * z))
        hbb = float(np.mean(w)) + l2
        det = haa * hbb - hab * hab
        if abs(det) < 1e-12:
            break
        da = -(hbb * ga - hab * gb) / det
        db = -(-hab * ga + haa * gb) / det
        f0, step, moved = obj(a, b), 1.0, False
        for _ in range(30):
            na, nb = a + step * da, b + step * db
            if obj(na, nb) < f0 - 1e-12:
                a, b, moved = na, nb, True
                break
            step *= 0.5
        if not moved:
            break
    return float(a), float(b)


def calib_diag(p, y, bins: int = 10) -> dict:
    """Honest calibration report: signed mean gap (pts) + expected calib error."""
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(p)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (p >= lo) & (p <= hi if i == bins - 1 else p < hi)
        if mask.sum() > 0:
            ece += (mask.sum() / n) * abs(p[mask].mean() - y[mask].mean())
    return {"mean_gap_pts": round(float(np.mean(p - y)) * 100, 2),
            "ece": round(float(ece), 4)}


def evaluate(K, C, L, chosen) -> dict:
    """Accuracy / cost / latency percentiles for a per-query chosen-index vec."""
    rows = np.arange(K.shape[0])
    lat = L.values[rows, chosen]
    return {
        "accuracy_pct": round(float(K.values[rows, chosen].mean() * 100), 2),
        "avg_cost_per_query": round(float(C.values[rows, chosen].mean()), 6),
        "avg_latency_s": round(float(lat.mean()), 3),
        "p50_latency_s": round(float(np.percentile(lat, 50)), 3),
        "p95_latency_s": round(float(np.percentile(lat, 95)), 3),
        "p99_latency_s": round(float(np.percentile(lat, 99)), 3),
    }


# ------------------------------------------------------------------- main
def main():
    matrix = pd.read_csv(OUT_DIR / "routing_matrix.csv")
    meta = (pd.read_csv(OUT_DIR / "query_meta.csv")
            .drop_duplicates("query_id").set_index("query_id"))
    K = matrix.pivot(index="query_id", columns="model_name", values="correct")[MODELS]
    C = matrix.pivot(index="query_id", columns="model_name", values="cost")[MODELS]
    L = matrix.pivot(index="query_id", columns="model_name", values="latency")[MODELS]

    tr, va, _te, _tier = load_splits()
    z = np.load(WEIGHTS_PATH, allow_pickle=False)
    W, b, idf = z["W"], z["b"], z["idf"]
    classes = [str(c) for c in z["classes"]]
    prior = {c: z[f"prior_{c}"] for c in classes}
    t_star = float(z["t_star"])

    # ---- MEASURED train-split statistics (the only numbers the router uses) --
    K_tr, C_tr, L_tr = K.loc[tr], C.loc[tr], L.loc[tr]
    acc = K_tr.mean().values.astype(float)          # per-model train accuracy
    cost = C_tr.mean().values.astype(float)         # per-model avg cost/query
    lat = L_tr.mean().values.astype(float)          # per-model avg latency (s)
    norm = Norm.from_stats(cost, lat)
    floor90 = QUALITY_FLOOR * acc[SI]               # absolute resolved floor
    flagship_lat = float(lat[SI])                   # measured always-strongest s

    # ---- raw head logits on train + val ------------------------------------
    meta_tr, meta_va = meta.loc[tr], meta.loc[va]
    X_tr = make_X(meta_tr["origin_query"], meta_tr["dataset_name"], idf, prior)[0]
    X_va = make_X(meta_va["origin_query"], meta_va["dataset_name"], idf, prior)[0]
    z_tr = X_tr @ W + b
    z_va = X_va @ W + b
    y_tr = K_tr.values.astype(float)

    # ---- fit Platt calibration on TRAIN, verify on VAL ---------------------
    calib, cal_a, cal_b = {}, [], []
    p_tr_cal = np.zeros_like(z_tr)
    p_va_cal = np.zeros_like(z_va)
    for m, name in enumerate(MODELS):
        a, bb = fit_platt(z_tr[:, m], y_tr[:, m])
        cal_a.append(a)
        cal_b.append(bb)
        p_tr_cal[:, m] = platt(z_tr[:, m], a, bb)
        p_va_cal[:, m] = platt(z_va[:, m], a, bb)
        calib[name] = {
            "a": round(a, 6), "b": round(bb, 6),
            "train": calib_diag(p_tr_cal[:, m], y_tr[:, m]),
            "val": calib_diag(p_va_cal[:, m], K.loc[va, name].values.astype(float)),
        }

    # ---- Pareto frontiers over measured train stats ------------------------
    stats = {"quality": acc, "cost": cost, "latency": lat}
    pol = load_policy()
    approved = set(pol.get("deployment", {}).get("approved_for_sensitive", []))
    priv_keep = [mname in approved for mname in MODELS]
    frontiers = {
        "global": model_frontier(MODELS, stats),
        "quality_floor": model_frontier(MODELS, stats, keep=list(acc >= floor90)),
        "privacy_approved": model_frontier(MODELS, stats, keep=priv_keep),
    }

    # ---- resolve + VERIFY each mode on VALIDATION --------------------------
    K_va, C_va, L_va = K.loc[va], C.loc[va], L.loc[va]
    floor_pct = QUALITY_FLOOR * K_va[STRONGEST].mean() * 100
    all_elig = np.ones(len(MODELS), dtype=bool)
    priv_elig = np.array(priv_keep, dtype=bool)

    modes_out, val_mix = {}, {}
    for key in MODE_ORDER:
        spec = MODES[key]
        elig = priv_elig if spec.privacy_restricted else all_elig
        # POLICY-level floor target (verified on val below) - NOT a per-query
        # gate. The per-query HARD floor stays a runtime opt-in via the API
        # `quality_floor` / UI slider, so the modes can span the real
        # cost/quality spectrum instead of all collapsing to the strong models.
        if spec.quality_floor_rule == "floor90":
            policy_floor_pct = round(float(floor_pct), 2)
        elif spec.quality_floor_rule == "strongest":
            policy_floor_pct = round(float(K_va[STRONGEST].mean() * 100), 2)
        else:
            policy_floor_pct = None
        lb = flagship_lat if spec.latency_budget_rule == "flagship_latency" else None
        policy = Policy(key, elig, spec.lambda_cost, spec.lambda_latency, None, lb)

        chosen = np.array([
            select(p_va_cal[i], acc, cost, lat, policy, norm)["chosen"]
            for i in range(len(va))
        ], dtype=int)
        met = evaluate(K_va, C_va, L_va, chosen)
        mix = (pd.Series([MODELS[c] for c in chosen]).value_counts()
               .reindex(MODELS).fillna(0).astype(int))
        val_mix[key] = mix.to_dict()
        meets = (None if policy_floor_pct is None
                 else bool(met["accuracy_pct"] >= policy_floor_pct))
        modes_out[key] = {
            "label": spec.label,
            "description": spec.description,
            "lambda_cost": spec.lambda_cost,
            "lambda_latency": spec.lambda_latency,
            "quality_floor_rule": spec.quality_floor_rule,
            "policy_quality_floor_pct": policy_floor_pct,
            "latency_budget_rule": spec.latency_budget_rule,
            "latency_budget_ms": (round(float(lb) * 1000, 1) if lb is not None else None),
            "privacy_restricted": spec.privacy_restricted,
            "eligible_models": [MODELS[i] for i in np.where(elig)[0]],
            "val": met,
            "val_meets_floor": meets,
            "val_model_mix": mix.to_dict(),
            "notes": spec.notes,
        }
        ok = "n/a" if meets is None else ("OK" if meets else "--")
        print(f"mode {key:9s} val acc={met['accuracy_pct']:6.2f}%  "
              f"cost=${met['avg_cost_per_query']:.6f}  "
              f"lat={met['avg_latency_s']:.3f}s  p95={met['p95_latency_s']:.3f}s  "
              f"floor[{policy_floor_pct}]={ok}")

    # ---- legacy cascade on the SAME val split (for the default-router call) --
    legacy_chosen = route_cascade(sigmoid(z_va), t_star)
    legacy_val = evaluate(K_va, C_va, L_va, legacy_chosen)
    legacy_mix = (pd.Series([MODELS[c] for c in legacy_chosen]).value_counts()
                  .reindex(MODELS).fillna(0).astype(int).to_dict())
    print(f"\nlegacy (t*={t_star:.2f}) val acc={legacy_val['accuracy_pct']:.2f}%  "
          f"cost=${legacy_val['avg_cost_per_query']:.6f}  "
          f"lat={legacy_val['avg_latency_s']:.3f}s")

    artifact = {
        "_meta": {
            "generated_by": "python -m routing.tune_mo",
            "provenance": (
                "Heads frozen from routing/models/router_weights.npz. Measured "
                "per-model accuracy/cost/latency and Platt calibration are fit "
                "on the TRAIN split; modes are VERIFIED on VALIDATION; the TEST "
                "split is sealed (see routing.eval_mo). No value is invented."
            ),
            "splits": {"train": len(tr), "val": len(va)},
            "strongest_model": STRONGEST,
            "quality_floor_fraction": QUALITY_FLOOR,
            "resolved_floor90": round(float(floor90), 4),
            "flagship_latency_ms": round(flagship_lat * 1000, 1),
            "val_floor_pct": round(float(floor_pct), 2),
        },
        "measured_train_stats": {
            name: {
                "accuracy": round(float(acc[i]), 4),
                "cost": round(float(cost[i]), 6),
                "latency_s": round(float(lat[i]), 3),
                "latency_ms": round(float(lat[i]) * 1000, 1),
            } for i, name in enumerate(MODELS)
        },
        "normalization": {
            "cost_min": norm.cost_min, "cost_max": norm.cost_max,
            "latency_min": norm.latency_min, "latency_max": norm.latency_max,
        },
        "calibration": calib,
        "frontiers": frontiers,
        "modes": modes_out,
        "mode_order": MODE_ORDER,
        "legacy_val": {**legacy_val, "val_model_mix": legacy_mix, "t_star": t_star},
        # The legacy cascade keeps the published, test-verified headline
        # numbers, so it stays the production default; the multi-objective
        # router is exposed as an experimental/advanced mode. Decided from the
        # validation evidence printed above, never from an unrun claim.
        "default_router": DEFAULT_ROUTER,
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ARTIFACT_PATH, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print(f"\nwrote {ARTIFACT_PATH} ({ARTIFACT_PATH.stat().st_size / 1e3:.1f} KB)")
    print(f"frontiers: global={frontiers['global']}")
    print(f"           quality_floor={frontiers['quality_floor']}")
    print(f"           privacy_approved={frontiers['privacy_approved']}")


if __name__ == "__main__":
    main()
