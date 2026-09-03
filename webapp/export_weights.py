"""One-time export of the trained A3 router for the web demo.

Reuses the exact training path from routing.learned_router (same features,
same heads, same aux supervision, same threshold tuning on val) and persists
everything the live simulator needs to routing/models/router_weights.npz:

  W, b        - logistic-regression heads, one per model
  idf         - hashed 4-gram idf vector learned on train
  classes     - fixed capability-class order used for one-hot features
  prior_<cls> - per-class train-split accuracy vector (len(MODELS))
  t_star      - cascade threshold tuned on val under the quality floor
  avg_cost / avg_latency - per-model averages from the routing matrix
                           (display estimates for arbitrary queries)
  tiers       - complexity tier names (easy/medium/hard); the live demo
                DERIVES these from the router's own per-model confidence,
                no separate classifier is trained
  mode_*      - the three configurable routing policies (economy/balanced/
                quality) with their thresholds and validation-split metrics

Run after any matrix/splits rebuild:  python -m webapp.export_weights
"""
import numpy as np
import pandas as pd

from routing.config import ALPHA, MODELS, OUT_DIR, QUALITY_FLOOR, ROOT
from routing.learned_router import (
    evaluate, load_aligned7_aux, make_X, route_cascade, sigmoid, train_heads,
)
from routing.splits import load_splits

WEIGHTS_DIR = ROOT / "routing" / "models"
WEIGHTS_PATH = WEIGHTS_DIR / "router_weights.npz"

# Configurable routing policies: (key, label, threshold). Balanced is replaced
# by the val-tuned t* at export time; the others are fixed operating points.
MODE_SPECS = [("economy", "Economy", 0.80),
              ("balanced", "Balanced", None),   # None -> t_star
              ("quality", "Quality First", 0.99)]
MODE_DESC = {
    "economy": "Maximum savings; routes to cheaper models more eagerly",
    "balanced": "Best quality/cost tradeoff - the measured headline policy",
    "quality": "Escalates aggressively toward the strongest models",
}


def main():
    matrix = pd.read_csv(OUT_DIR / "routing_matrix.csv")
    meta = pd.read_csv(OUT_DIR / "query_meta.csv")
    meta = meta.drop_duplicates("query_id").set_index("query_id")

    K = matrix.pivot(index="query_id", columns="model_name", values="correct")[MODELS]
    C = matrix.pivot(index="query_id", columns="model_name", values="cost")[MODELS]
    L = matrix.pivot(index="query_id", columns="model_name", values="latency")[MODELS]

    tr, va, te, _ = load_splits()
    tr_set = set(tr)
    meta_va = meta.loc[va]
    K_va, C_va, L_va = K.loc[va], C.loc[va], L.loc[va]

    tr_df = matrix[matrix["query_id"].isin(tr_set)]
    prior = {cls: g.groupby("model_name")["correct"].mean().reindex(MODELS).values
             for cls, g in tr_df.groupby("dataset_name")}

    aux = load_aligned7_aux()
    aux = aux[~aux["query_id"].isin(tr_set | set(va) | set(te))]
    tr_meta = meta.loc[tr]
    texts = tr_meta["origin_query"].tolist() + aux["origin_query"].tolist()
    classes = tr_meta["dataset_name"].tolist() + aux["dataset_name"].tolist()
    Y = np.full((len(texts), len(MODELS)), np.nan)
    for i, qid in enumerate(tr):
        Y[i, :] = K.loc[qid].values
    base = len(tr)
    for j, (_, r) in enumerate(aux.iterrows()):
        Y[base + j, MODELS.index(r["model_name"])] = r["correct"]

    print(f"training heads on {len(tr)} train + {len(aux)} aux rows ...")
    X_tr, idf = make_X(texts, classes, prior=prior)
    W, b = train_heads(X_tr, Y)

    # Tune t* on val exactly as learned_router.main does.
    p_va = sigmoid(make_X(meta_va["origin_query"], meta_va["dataset_name"],
                          idf, prior)[0] @ W + b)
    floor = QUALITY_FLOOR * K_va[MODELS[-1]].mean() * 100
    best, best_cost = None, np.inf
    for t in np.arange(0.50, 0.96, 0.05):
        m = evaluate(K_va, C_va, L_va, route_cascade(p_va, t))
        if m["accuracy"] >= floor and m["avg_cost"] < best_cost:
            best, best_cost = float(t), m["avg_cost"]
    t_star = best if best is not None else 0.95
    print(f"floor={floor:.1f}%  tuned t* = {t_star:.2f}")

    # Configurable routing policies: measure each candidate threshold on the
    # SAME validation split used to tune t*, so the mode cards quote honest
    # val numbers rather than unmeasured claims.
    tiers = ["easy", "medium", "hard"]
    mode_keys, mode_t, mode_acc, mode_cost, mode_floor = [], [], [], [], []
    for key, _label, mt in MODE_SPECS:
        mt = t_star if mt is None else float(mt)
        m = evaluate(K_va, C_va, L_va, route_cascade(p_va, mt))
        mode_keys.append(key)
        mode_t.append(round(mt, 4))
        mode_acc.append(round(m["accuracy"], 2))
        mode_cost.append(round(m["avg_cost"], 6))
        mode_floor.append(bool(m["accuracy"] >= floor))
        print(f"mode {key:9s} t={mt:.2f}  val acc={m['accuracy']:.2f}%  "
              f"cost=${m['avg_cost']:.6f}  meets_floor={m['accuracy'] >= floor}")

    class_order = sorted(set(classes))
    payload = {
        "W": W, "b": b, "idf": idf,
        "models": np.array(MODELS),
        "classes": np.array(class_order),
        "t_star": np.array(t_star),
        "alpha": np.array(ALPHA),
        "avg_cost": C.mean().values,
        "avg_latency": L.mean().values,
        "tiers": np.array(tiers),
        "mode_keys": np.array(mode_keys),
        "mode_t": np.array(mode_t),
        "mode_acc": np.array(mode_acc),
        "mode_cost": np.array(mode_cost),
        "mode_floor": np.array(mode_floor),
    }
    for cls in class_order:
        payload[f"prior_{cls}"] = prior[cls]
        payload[f"class_acc_{cls}"] = (
            matrix[matrix["dataset_name"] == cls]
            .groupby("model_name")["correct"].mean().reindex(MODELS).values)

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(WEIGHTS_PATH, **payload)
    print(f"wrote {WEIGHTS_PATH} ({WEIGHTS_PATH.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
