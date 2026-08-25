"""Tasks R1+R2: routing baselines for the learned router (A3) and oracle (A2).

Protocol (matches U4): every policy is fitted on the TRAIN split only,
any confidence threshold is tuned on VAL under the quality floor, and the
printed table is the official TEST split. All policies are scored through
routing.metrics.build_report so the thesis tables line up exactly.

R1 static   : always-strongest, always-cheapest, random, class-based
R2 dynamic  : prior-cascade  (class-prior confidence, cheap->strong)
              knn-cascade    (k-nearest train neighbours per model, cheap->strong)
              learned-cascade (A3 heads re-trained here so one table + the
              plots in R3 can share a single source of truth)
"""
import numpy as np
import pandas as pd

from routing.config import MODELS, OUT_DIR, QUALITY_FLOOR, RESULTS_DIR, SEED
from routing.learned_router import (load_aligned7_aux, make_X, route_cascade,
                                    sigmoid, train_heads)
from routing.metrics import build_report, evaluate, oracle_choice
from routing.oracle import load_wide
from routing.splits import load_splits

KNN_K = 15
T_GRID = np.arange(0.50, 0.96, 0.05)


# ------------------------------------------------------------------ context
def load_context():
    """Wide matrices, official splits, query meta, train class prior."""
    K, C, L = load_wide()
    tr, va, te, tier_map = load_splits()
    meta = pd.read_csv(OUT_DIR / "query_meta.csv")
    meta = meta.drop_duplicates("query_id").set_index("query_id")

    tr_cls = meta.loc[tr, "dataset_name"]
    prior = {cls: K.loc[idx].mean().values
             for cls, idx in tr_cls.groupby(tr_cls).groups.items()}
    return K, C, L, tr, va, te, tier_map, meta, prior


# ------------------------------------------------------------------ R1
def static_policies(n):
    rng = np.random.default_rng(SEED)
    return {
        "always-strongest": np.full(n, len(MODELS) - 1, dtype=int),
        "always-cheapest": np.zeros(n, dtype=int),
        "random": rng.integers(0, len(MODELS), n),
    }


def class_based_policy(qids, meta, prior):
    """Per class: cheapest model whose TRAIN acc >= floor * best-in-class."""
    pick = {}
    for cls, acc in prior.items():
        feasible = np.where(acc >= QUALITY_FLOOR * acc.max())[0]
        pick[cls] = int(feasible.min())          # MODELS ordered cheap->strong
    cls = meta.loc[qids, "dataset_name"]
    return cls.map(pick).to_numpy(dtype=int)


# ------------------------------------------------------------------ R2
def prior_cascade_scores(qids, meta, prior):
    cls = meta.loc[qids, "dataset_name"].tolist()
    return np.stack([prior[c] for c in cls])     # n x 8 class confidence


def knn_scores(qids, tr, meta, K):
    """P(correct_m | q) = mean correctness of the KNN_K nearest train queries
    (cosine over hashed char 4-gram tf-idf). Train-only information."""
    X_tr, idf = make_X(meta.loc[tr, "origin_query"].tolist(),
                       meta.loc[tr, "dataset_name"].tolist())
    X_q, _ = make_X(meta.loc[qids, "origin_query"].tolist(),
                    meta.loc[qids, "dataset_name"].tolist(), idf=idf)
    sim = X_q @ X_tr.T          # same feature layout both sides
    topk = np.argsort(-sim, axis=1)[:, :KNN_K]
    return K.loc[tr].values[topk].mean(axis=1)   # n x 8


def tune_threshold(P_va, K_va, C_va, L_va, name):
    """Grid-search t on val under the quality floor; return (t*, curve)."""
    floor = QUALITY_FLOOR * K_va[MODELS[-1]].mean() * 100
    best, best_cost, curve = None, np.inf, []
    for t in T_GRID:
        m = evaluate(K_va, C_va, L_va, route_cascade(P_va, t))
        ok = m["accuracy"] >= floor
        curve.append((name, round(float(t), 2), round(m["accuracy"], 2),
                      round(m["avg_cost"], 6), bool(ok)))
        if ok and m["avg_cost"] < best_cost:
            best, best_cost = float(t), m["avg_cost"]
    return (best if best is not None else 0.95), curve


# ------------------------------------------------- learned cascade (A3 reuse)
def train_learned_heads(K, tr, va, te, meta, prior):
    """Same training recipe as learned_router.main, exposed for reuse."""
    aux = load_aligned7_aux()
    aux = aux[~aux["query_id"].isin(set(tr) | set(va) | set(te))]
    texts = meta.loc[tr, "origin_query"].tolist() + aux["origin_query"].tolist()
    classes = meta.loc[tr, "dataset_name"].tolist() + aux["dataset_name"].tolist()
    Y = np.full((len(texts), len(MODELS)), np.nan)
    Y[:len(tr)] = K.loc[tr].values
    for j, r in enumerate(aux.itertuples(index=False)):
        Y[len(tr) + j, MODELS.index(r.model_name)] = r.correct
    X_tr, idf = make_X(texts, classes, prior=prior)
    W, b = train_heads(X_tr, Y)

    def scores(qids):
        X = make_X(meta.loc[qids, "origin_query"].tolist(),
                   meta.loc[qids, "dataset_name"].tolist(), idf, prior)[0]
        return sigmoid(X @ W + b)
    return scores


# --------------------------------------------------------------------- main
def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    K, C, L, tr, va, te, tier_map, meta, prior = load_context()
    K_va, C_va, L_va = K.loc[va], C.loc[va], L.loc[va]
    K_te, C_te, L_te = K.loc[te], C.loc[te], L.loc[te]

    policies = static_policies(len(te))
    policies["class-based"] = class_based_policy(te, meta, prior)

    curves = []
    tuned = {}
    for name, P_va in [("prior-cascade", prior_cascade_scores(va, meta, prior)),
                       ("knn-cascade", knn_scores(va, tr, meta, K))]:
        t, curve = tune_threshold(P_va, K_va, C_va, L_va, name)
        curves += curve
        tuned[name] = t

    learned = train_learned_heads(K, tr, va, te, meta, prior)
    t, curve = tune_threshold(learned(va), K_va, C_va, L_va, "learned-cascade")
    curves += curve
    tuned["learned-cascade"] = t

    for name, P_te in [("prior-cascade", prior_cascade_scores(te, meta, prior)),
                       ("knn-cascade", knn_scores(te, tr, meta, K)),
                       ("learned-cascade", learned(te))]:
        policies[f"{name} (t={tuned[name]:.2f})"] = \
            route_cascade(P_te, tuned[name])

    policies["oracle"] = oracle_choice(K_te, C_te, L_te)

    report = build_report(policies, K_te, C_te, L_te)
    report.to_csv(RESULTS_DIR / "baselines_report.csv", index=False)
    pd.DataFrame(curves, columns=["policy", "t", "val_accuracy_pct",
                                  "val_avg_cost", "meets_floor"]) \
        .to_csv(RESULTS_DIR / "threshold_curves.csv", index=False)

    np.savez(RESULTS_DIR / "policy_choices.npz",
             test_qids=np.array(te, dtype=object),
             **{k.replace("-", "_").replace(" ", "_").replace("=", "")
                .replace("(", "").replace(")", "").replace(".", "_"): v
                for k, v in policies.items()})

    print(f"baselines on official test split ({len(te)} queries); "
          f"thresholds tuned on val under floor "
          f"{QUALITY_FLOOR * K_va[MODELS[-1]].mean() * 100:.1f}%")
    print(report.to_string(index=False))
    print("\ntuned thresholds:",
          {k: round(v, 2) for k, v in tuned.items()})

    for name in ["knn-cascade", "learned-cascade"]:
        key = [k for k in policies if k.startswith(name)][0]
        sel = pd.Series([MODELS[i] for i in policies[key]]).value_counts()
        print(f"\nmodel selection ({key}, test):")
        print(sel.to_string())


if __name__ == "__main__":
    main()
