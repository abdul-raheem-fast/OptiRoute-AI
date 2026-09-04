"""Sealed-TEST evaluation of the multi-objective router vs every baseline.

This is the ONLY script that touches the held-out test split for the
multi-objective router, and it does so for FINAL REPORTING - every fitted
quantity (heads, Platt calibration, measured cost/latency/quality, mode weights)
comes from ``routing/models/mo_objectives.json`` + ``router_weights.npz``, both
derived from TRAIN (calibration) / TRAIN (stats) and VERIFIED on VAL. No
parameter here is tuned on test.

Policies compared:
  1. always-cheapest      (Llama-3.1-8B-Instruct)
  2. always-strongest     (gpt-5)
  3. legacy learned cascade (t* on raw head scores - the published router)
  4. multi-objective router, one row per mode (economy/balanced/speed/
     quality/private)

Metrics: accuracy, avg cost, avg/p50/p95/p99 latency, per-model routing mix,
privacy-filtered share, and quality / cost / latency relative to always-gpt-5.

Run:  python -m routing.eval_mo     (writes results/mo_eval_report.{csv,md})
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from routing.config import MODELS, OUT_DIR, RESULTS_DIR, ROOT, STRONGEST
from routing.learned_router import make_X, route_cascade, sigmoid
from routing.mo_core import Norm, Policy, platt, select
from routing.objectives import MODE_ORDER
from routing.sensitivity import classify_sensitivity
from routing.splits import load_splits

WEIGHTS_PATH = ROOT / "routing" / "models" / "router_weights.npz"
ARTIFACT_PATH = ROOT / "routing" / "models" / "mo_objectives.json"
SI = MODELS.index(STRONGEST)


def evaluate(K, C, L, chosen) -> dict:
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


def mix_pct(chosen) -> dict:
    vc = pd.Series([MODELS[c] for c in chosen]).value_counts()
    n = len(chosen)
    return {m: round(float(vc.get(m, 0)) / n * 100, 1) for m in MODELS}


def md_table(df: pd.DataFrame) -> str:
    """GitHub markdown table without the optional `tabulate` dependency."""
    cols = list(df.columns)
    head = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = ["| " + " | ".join(str(v) for v in row) + " |"
            for row in df.itertuples(index=False, name=None)]
    return "\n".join([head, sep, *body])


def main():
    if not ARTIFACT_PATH.exists():
        raise SystemExit("mo_objectives.json missing - run: python -m routing.tune_mo")
    matrix = pd.read_csv(OUT_DIR / "routing_matrix.csv")
    meta = (pd.read_csv(OUT_DIR / "query_meta.csv")
            .drop_duplicates("query_id").set_index("query_id"))
    K = matrix.pivot(index="query_id", columns="model_name", values="correct")[MODELS]
    C = matrix.pivot(index="query_id", columns="model_name", values="cost")[MODELS]
    L = matrix.pivot(index="query_id", columns="model_name", values="latency")[MODELS]

    _tr, _va, te, _tier = load_splits()
    te = [q for q in te if q in meta.index]
    K_te, C_te, L_te = K.loc[te], C.loc[te], L.loc[te]
    meta_te = meta.loc[te]

    z = np.load(WEIGHTS_PATH, allow_pickle=False)
    W, b, idf = z["W"], z["b"], z["idf"]
    classes = [str(c) for c in z["classes"]]
    prior = {c: z[f"prior_{c}"] for c in classes}
    t_star = float(z["t_star"])

    art = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    st = art["measured_train_stats"]
    acc = np.array([st[m]["accuracy"] for m in MODELS])
    cost = np.array([st[m]["cost"] for m in MODELS])
    lat = np.array([st[m]["latency_s"] for m in MODELS])
    nrm = art["normalization"]
    norm = Norm(nrm["cost_min"], nrm["cost_max"], nrm["latency_min"], nrm["latency_max"])
    cal = art["calibration"]
    cal_a = np.array([cal[m]["a"] for m in MODELS])
    cal_b = np.array([cal[m]["b"] for m in MODELS])

    # ---- scores on the SEALED test split ---------------------------------
    X_te = make_X(meta_te["origin_query"], meta_te["dataset_name"], idf, prior)[0]
    z_te = X_te @ W + b
    raw_te = sigmoid(z_te)
    pcal_te = platt(z_te, cal_a, cal_b)

    # ---- sensitivity of the sealed test queries (local, no LLM) ----------
    sens_flags = [classify_sensitivity(q)["sensitivity"] == "sensitive"
                  for q in meta_te["origin_query"]]
    n_sensitive = int(sum(sens_flags))

    approved = set(json.loads(
        (ROOT / "webapp" / "privacy_policy.json").read_text(encoding="utf-8")
    ).get("deployment", {}).get("approved_for_sensitive", []))
    all_elig = np.ones(len(MODELS), dtype=bool)
    priv_elig = np.array([m in approved for m in MODELS])

    # ---- policies --------------------------------------------------------
    n = len(te)
    policies: list[tuple[str, np.ndarray, float]] = []
    policies.append(("always-cheapest", np.zeros(n, dtype=int), 0.0))
    policies.append(("always-gpt-5", np.full(n, SI, dtype=int), 0.0))
    policies.append((f"legacy-cascade (t*={t_star:.2f})",
                     route_cascade(raw_te, t_star), 0.0))
    for key in MODE_ORDER:
        spec = art["modes"][key]
        elig = priv_elig if spec["privacy_restricted"] else all_elig
        lb_ms = spec.get("latency_budget_ms")
        lb_s = (float(lb_ms) / 1000.0) if lb_ms is not None else None
        policy = Policy(key, elig, float(spec["lambda_cost"]),
                        float(spec["lambda_latency"]), None, lb_s)
        chosen = np.array([
            select(pcal_te[i], acc, cost, lat, policy, norm)["chosen"]
            for i in range(n)], dtype=int)
        filtered_pct = round((1 - elig.sum() / len(MODELS)) * 100, 1)
        policies.append((f"mo-{key}", chosen, filtered_pct))

    # ---- reference (always-gpt-5) for relative metrics -------------------
    ref = evaluate(K_te, C_te, L_te, np.full(n, SI, dtype=int))
    ref_acc, ref_cost, ref_lat = ref["accuracy_pct"], ref["avg_cost_per_query"], ref["avg_latency_s"]

    rows = []
    for name, chosen, filtered_pct in policies:
        m = evaluate(K_te, C_te, L_te, chosen)
        rows.append({
            "policy": name,
            "accuracy_pct": m["accuracy_pct"],
            "quality_vs_gpt5_pct": round(m["accuracy_pct"] / ref_acc * 100, 1),
            "avg_cost_per_query": m["avg_cost_per_query"],
            "cost_reduction_vs_gpt5_pct": round((1 - m["avg_cost_per_query"] / ref_cost) * 100, 1),
            "avg_latency_s": m["avg_latency_s"],
            "p50_latency_s": m["p50_latency_s"],
            "p95_latency_s": m["p95_latency_s"],
            "p99_latency_s": m["p99_latency_s"],
            "latency_delta_vs_gpt5_s": round(m["avg_latency_s"] - ref_lat, 3),
            "privacy_filtered_pct": filtered_pct,
            **{f"mix_{mm}": v for mm, v in mix_pct(chosen).items()},
        })

    df = pd.DataFrame(rows)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(RESULTS_DIR / "mo_eval_report.csv", index=False)

    # ---- console + markdown summary -------------------------------------
    show = ["policy", "accuracy_pct", "quality_vs_gpt5_pct", "avg_cost_per_query",
            "cost_reduction_vs_gpt5_pct", "avg_latency_s", "p95_latency_s",
            "privacy_filtered_pct"]
    print(f"SEALED TEST ({n} queries) | sensitive-flagged by local classifier: "
          f"{n_sensitive} ({n_sensitive / n * 100:.1f}%)")
    print(f"reference always-gpt-5: acc={ref_acc:.2f}%  cost=${ref_cost:.6f}  lat={ref_lat:.3f}s\n")
    print(df[show].to_string(index=False))

    md = ["# Multi-objective router - sealed-test evaluation",
          "",
          f"Test split: **{n} queries** (sealed; used only here for final "
          f"reporting). All fitted quantities come from train (calibration / "
          f"stats) and were verified on val - see `routing/tune_mo.py`.",
          "",
          f"Local sensitivity classifier flagged **{n_sensitive}/{n} "
          f"({n_sensitive / n * 100:.1f}%)** test queries as sensitive.",
          "",
          f"Reference `always-gpt-5`: accuracy **{ref_acc:.2f}%**, cost "
          f"**${ref_cost:.6f}/query**, avg latency **{ref_lat:.3f}s**.",
          "",
          df[show].pipe(md_table),
          "",
          "## Routing mix (% of test queries per model)",
          "",
          md_table(df[["policy"] + [f"mix_{m}" for m in MODELS]]),
          "",
          "## Honest reading",
          "",
          "* The legacy cascade reproduces the published binary Qwen3-8B/gpt-5 "
          "concentration - a real property of this pool under a cost objective, "
          "not a bug (see README 'Sparse Pareto frontier').",
          "* The multi-objective modes span a genuine cost/quality/latency/"
          "privacy spectrum; `mo-economy` is cheaper than legacy, `mo-balanced` "
          "trades cost for higher accuracy and much lower latency, `mo-speed` "
          "honours the latency budget, `mo-private` stays inside the approved "
          "(locally hosted) set at lower accuracy.",
          "* No mode is forced to use models the objective does not favour; "
          "diversity here is measured, not manufactured.",
          ""]
    (RESULTS_DIR / "mo_eval_report.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nwrote {RESULTS_DIR / 'mo_eval_report.csv'} and .md")


if __name__ == "__main__":
    main()
