"""Task A2: per-query oracle routing policy and headline results.

Oracle definition: for every query q,
    m*(q) = argmin_m [ C_m(q) + alpha * L_m(q) ]  subject to  correct_m(q) = 1
If no model answers q correctly, the oracle falls back to the cheapest model
(the query is lost either way; cost is minimized).

The oracle is a hindsight upper bound - it sees ground truth. Practical
routers (baselines R1/R2, learned router A3) are compared against it; the
difference is the "oracle gap" (RQ5).
"""
import numpy as np
import pandas as pd

from routing.config import ALPHA_SWEEP, CHEAPEST, MODELS, OUT_DIR, RESULTS_DIR, STRONGEST


def load_wide():
    """Return (K, C, L) wide DataFrames indexed by query_id, cols = MODELS."""
    df = pd.read_csv(OUT_DIR / "routing_matrix.csv",
                     usecols=["query_id", "model_name", "correct", "cost", "latency"])
    K = df.pivot(index="query_id", columns="model_name", values="correct")[MODELS]
    C = df.pivot(index="query_id", columns="model_name", values="cost")[MODELS]
    L = df.pivot(index="query_id", columns="model_name", values="latency")[MODELS]
    return K, C, L


def policy_metrics(K, C, L, chosen_idx):
    """Aggregate metrics for a per-query model choice (column indices)."""
    n = K.shape[0]
    rows = np.arange(n)
    acc = K.values[rows, chosen_idx].mean()
    cost = C.values[rows, chosen_idx].mean()
    lat = L.values[rows, chosen_idx].mean()
    return acc, cost, lat


def static_policy(K, C, L, model):
    idx = np.full(K.shape[0], MODELS.index(model), dtype=int)
    return policy_metrics(K, C, L, idx)


def oracle_policy(K, C, L, alpha):
    """Return (chosen_idx, n_queries_with_no_correct_model)."""
    obj = (C + alpha * L).where(K.values == 1, np.inf)
    chosen = obj.values.argmin(axis=1)  # all-inf rows -> 0 = cheapest model
    no_correct = int(np.isinf(obj.values).all(axis=1).sum())
    return chosen, no_correct


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    K, C, L = load_wide()
    n_q = K.shape[0]

    strongest = static_policy(K, C, L, STRONGEST)
    cheapest = static_policy(K, C, L, CHEAPEST)

    rows = [
        ("always-strongest (%s)" % STRONGEST, None, *strongest),
        ("always-cheapest (%s)" % CHEAPEST, None, *cheapest),
    ]
    for alpha in ALPHA_SWEEP:
        chosen, no_correct = oracle_policy(K, C, L, alpha)
        rows.append((f"oracle (alpha={alpha:g})", alpha,
                     *policy_metrics(K, C, L, chosen)))

    acc_s, cost_s, lat_s = strongest
    table = []
    for name, alpha, acc, cost, lat in rows:
        table.append({
            "policy": name,
            "accuracy": round(acc * 100, 2),
            "avg_cost_per_query": round(cost, 6),
            "avg_latency_s": round(lat, 3),
            "cost_reduction_vs_strongest_pct": round((1 - cost / cost_s) * 100, 1),
            "accuracy_gap_vs_strongest_pts": round((acc - acc_s) * 100, 2),
        })
    out = pd.DataFrame(table)
    out.to_csv(RESULTS_DIR / "oracle_report.csv", index=False)

    print(f"queries: {n_q} | models: {len(MODELS)}")
    print(out.to_string(index=False))

    _, no_correct = oracle_policy(K, C, L, 0.0)
    print(f"\nqueries with NO correct model among the 8: {no_correct} "
          f"({no_correct / n_q * 100:.1f}%) - oracle falls back to cheapest there")


if __name__ == "__main__":
    main()
