"""Task U4: shared evaluation metrics for all routing policies.

Every router (static baselines R1, cascade R2, learned A3, oracle A2) is
scored through the same functions so the paper tables are directly
comparable. Report columns:

  accuracy_pct                    held-out correctness of the routed choice
  quality_vs_strongest_pct        accuracy / always-strongest accuracy * 100
  avg_cost_per_query, avg_latency_s
  cost_reduction_vs_strongest_pct
  oracle_gap_pts                  accuracy shortfall vs the oracle (RQ5)
  meets_quality_floor             accuracy >= QUALITY_FLOOR * strongest (A_min)
"""
import numpy as np
import pandas as pd

from routing.config import ALPHA, MODELS, OUT_DIR, QUALITY_FLOOR


def evaluate(K, C, L, chosen):
    """Aggregate metrics for a per-query model choice (column indices)."""
    n = K.shape[0]
    rows = np.arange(n)
    return {
        "accuracy": K.values[rows, chosen].mean() * 100,
        "avg_cost": C.values[rows, chosen].mean(),
        "avg_latency": L.values[rows, chosen].mean(),
    }


def oracle_choice(K, C, L, alpha=ALPHA):
    """Hindsight oracle: argmin cost + alpha*latency among correct models."""
    obj = (C + alpha * L).where(K.values == 1, np.inf)
    return obj.values.argmin(axis=1)


def build_report(policies, K, C, L):
    """policies: ordered dict name -> chosen index array. Returns DataFrame."""
    base = {name: evaluate(K, C, L, ch) for name, ch in policies.items()}
    if "always-strongest" in base:
        acc_s, cost_s = base["always-strongest"]["accuracy"], base["always-strongest"]["avg_cost"]
    else:
        acc_s = max(m["accuracy"] for m in base.values())
        cost_s = min(m["avg_cost"] for m in base.values())
    oracle_acc = base["oracle"]["accuracy"] if "oracle" in base else None

    rows = []
    for name, m in base.items():
        row = {
            "policy": name,
            "accuracy_pct": round(m["accuracy"], 2),
            "quality_vs_strongest_pct": round(m["accuracy"] / acc_s * 100, 1),
            "avg_cost_per_query": round(m["avg_cost"], 6),
            "avg_latency_s": round(m["avg_latency"], 3),
            "cost_reduction_vs_strongest_pct":
                round((1 - m["avg_cost"] / cost_s) * 100, 1),
            "meets_quality_floor": bool(m["accuracy"] >= QUALITY_FLOOR * acc_s),
        }
        row["oracle_gap_pts"] = (
            round((oracle_acc - m["accuracy"]), 2) if oracle_acc is not None else None)
        rows.append(row)
    return pd.DataFrame(rows)


def breakdown(K, chosen, splits_df, by="tier"):
    """Per-stratum accuracy of a policy on the split rows of K (RQ4)."""
    tiers = splits_df.set_index("query_id")[by]
    out = []
    rows = np.arange(K.shape[0])
    correct = K.values[rows, chosen]
    for grp, idx in K.index.to_series().groupby(tiers):
        pos = [K.index.get_loc(q) for q in idx]
        out.append((grp, round(correct[pos].mean() * 100, 2), len(pos)))
    return pd.DataFrame(out, columns=[by, "accuracy_pct", "n"])


def main():
    """Self-check: reference policies on the official test split."""
    from routing.splits import load_splits
    matrix = pd.read_csv(OUT_DIR / "routing_matrix.csv")
    tr, va, te, _ = load_splits()
    K = matrix.pivot(index="query_id", columns="model_name", values="correct")[MODELS]
    C = matrix.pivot(index="query_id", columns="model_name", values="cost")[MODELS]
    L = matrix.pivot(index="query_id", columns="model_name", values="latency")[MODELS]
    K_te, C_te, L_te = K.loc[te], C.loc[te], L.loc[te]
    n = len(te)

    report = build_report({
        "always-strongest": np.full(n, len(MODELS) - 1),
        "always-cheapest": np.zeros(n, dtype=int),
        "oracle": oracle_choice(K_te, C_te, L_te),
    }, K_te, C_te, L_te)
    print(f"metrics self-check on official test split ({n} queries):")
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()
