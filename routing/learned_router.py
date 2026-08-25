"""Task A3: learned query-level router ("our method").

Design
------
At routing time the router may only use information available BEFORE any model
answers: the query text, its capability class, and benchmark-level statistics.
It trains one binary logistic-regression head per model,
P(correct_m | features), and routes with a learned-confidence cascade
(FrugalgPT-style):

    m(q) = cheapest model (cheap->strong) with P(correct_m) >= t,
           else the strongest model

The threshold t is tuned on the VALIDATION split under the constraint
accuracy >= QUALITY_FLOOR * always-strongest (the thesis target), minimizing
cost among thresholds that satisfy it. The full val curve is printed for
transparency.

Features (all knowable before dispatch):
  - capability-class one-hot + scalar text stats + hashed char 4-gram TF-IDF
  - class prior: each model's train-split accuracy within the query's class
Training data: aligned_8 train split + deduplicated aligned_7 extended set
(2.4x more supervision for the 7 models present there).

NOTE (splits): uses the official stratified splits from routing/splits.py
(task U1). Re-run this script whenever the splits or matrix are rebuilt.
"""
import csv
import hashlib

import numpy as np
import pandas as pd

from routing.config import ALIGNED7_DIR, ALPHA, MODELS, OUT_DIR, QUALITY_FLOOR, RESULTS_DIR
from routing.splits import load_splits

csv.field_size_limit(100000000)

D_HASH = 2048          # hashed char 4-gram dimensions
L2 = 1e-4
LR = 0.25
ITERS = 600


# ---------------------------------------------------------------- features
def _gram(text, i):
    h = hashlib.md5(text[i:i + 4].encode("utf-8", "ignore")).digest()
    return int.from_bytes(h[:4], "little") % D_HASH, (1 if h[4] % 2 == 0 else -1)


def hashed_tfidf(texts, idf=None):
    """Return (n x D) l2-normalized tf-idf matrix; idf learned if None."""
    n = len(texts)
    X = np.zeros((n, D_HASH), dtype=np.float64)
    for i, t in enumerate(texts):
        s = t.lower()
        for j in range(max(0, len(s) - 3)):
            idx, sign = _gram(s, j)
            X[i, idx] += sign
    X = np.abs(X)                      # signed hash -> tf
    if idf is None:
        df = (X > 0).mean(axis=0)
        idf = np.log((1 + n) / (1 + df * n)) + 1.0
    X *= idf
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return X / norms, idf


def scalar_features(texts, classes):
    t = pd.Series(texts).fillna("")
    f = pd.DataFrame()
    f["len_chars"] = np.log1p(t.str.len())
    f["len_words"] = np.log1p(t.str.split().str.len())
    f["digit_frac"] = t.apply(lambda s: sum(c.isdigit() for c in s) / max(1, len(s)))
    f["has_code"] = t.str.contains(r"```|def |import |function", regex=True).astype(float)
    f["n_question"] = t.str.count(r"\?")
    for cls in sorted(set(classes)):
        f[f"class_{cls}"] = (pd.Series(classes) == cls).astype(float)
    return f.values


def make_X(texts, classes, idf=None, prior=None):
    """prior: dict class -> np.array(len(MODELS)) train accuracies, or None."""
    tfidf, idf = hashed_tfidf(texts, idf)
    parts = [scalar_features(texts, classes), tfidf]
    if prior is not None:
        parts.append(np.stack([prior[c] for c in classes]))
    return np.hstack(parts), idf


# ------------------------------------------------------------ logistic reg
def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def train_heads(X, Y):
    """Y: n x 8 binary (NaN rows masked per column). Returns (W, b)."""
    n, d = X.shape
    W = np.zeros((d, len(MODELS)))
    b = np.zeros(len(MODELS))
    for _ in range(ITERS):
        P = sigmoid(X @ W + b)
        M = ~np.isnan(Y)
        diff = np.where(M, P - Y, 0.0)
        counts = M.sum(axis=0)
        G = (X.T @ diff) / counts + L2 * W
        gb = diff.sum(axis=0) / counts
        W -= LR * G
        b -= LR * gb
    return W, b


# ---------------------------------------------------------------- routing
def load_aligned7_aux():
    """Deduplicated aligned_7 rows as aux supervision (7 of 8 models)."""
    rows = []
    for model in MODELS:
        path = ALIGNED7_DIR / f"{model}.csv"
        if not path.exists():
            continue
        seen_model = set()
        with open(path, encoding="utf-8", errors="ignore") as f:
            for r in csv.DictReader(f):
                qid = r["query_id"]
                if qid in seen_model:
                    continue
                seen_model.add(qid)
                rows.append({"query_id": qid, "model_name": model,
                             "dataset_name": r["dataset_name"],
                             "origin_query": r["origin_query"],
                             "correct": int(float(r["correct"]))})
    return pd.DataFrame(rows)


def route_cascade(p, t):
    """Cheapest-first cascade: first model (cheap->strong) with p >= t,
    else the strongest model."""
    chosen = np.full(p.shape[0], len(MODELS) - 1, dtype=int)
    for m in range(len(MODELS) - 1, -1, -1):   # strong->cheap, cheaper overwrites
        chosen = np.where(p[:, m] >= t, m, chosen)
    return chosen


def evaluate(K, C, L, chosen):
    n = K.shape[0]
    rows = np.arange(n)
    return {
        "accuracy": K.values[rows, chosen].mean() * 100,
        "avg_cost": C.values[rows, chosen].mean(),
        "avg_latency": L.values[rows, chosen].mean(),
    }


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    matrix = pd.read_csv(OUT_DIR / "routing_matrix.csv")
    meta = pd.read_csv(OUT_DIR / "query_meta.csv")
    meta = meta.drop_duplicates("query_id").set_index("query_id")

    K = matrix.pivot(index="query_id", columns="model_name", values="correct")[MODELS]
    C = matrix.pivot(index="query_id", columns="model_name", values="cost")[MODELS]
    L = matrix.pivot(index="query_id", columns="model_name", values="latency")[MODELS]

    tr, va, te, _ = load_splits()
    tr_set = set(tr)
    meta_va, meta_te = meta.loc[va], meta.loc[te]
    K_va, C_va, L_va = K.loc[va], C.loc[va], L.loc[va]
    K_te, C_te, L_te = K.loc[te], C.loc[te], L.loc[te]

    # Class prior from the train split only (knowable before dispatch).
    tr_df = matrix[matrix["query_id"].isin(tr_set)]
    prior = {cls: g.groupby("model_name")["correct"].mean().reindex(MODELS).values
             for cls, g in tr_df.groupby("dataset_name")}

    # Training set = aligned_8 train + deduplicated aligned_7 aux rows.
    aux = load_aligned7_aux()
    aux = aux[~aux["query_id"].isin(tr_set | set(va) | set(te))]  # no leakage
    tr_meta = meta.loc[tr]
    texts = tr_meta["origin_query"].tolist() + aux["origin_query"].tolist()
    classes = tr_meta["dataset_name"].tolist() + aux["dataset_name"].tolist()
    Y = np.full((len(texts), len(MODELS)), np.nan)
    for i, qid in enumerate(tr):
        Y[i, :] = K.loc[qid].values
    base = len(tr)
    for j, (_, r) in enumerate(aux.iterrows()):
        Y[base + j, MODELS.index(r["model_name"])] = r["correct"]

    X_tr, idf = make_X(texts, classes, prior=prior)
    W, b = train_heads(X_tr, Y)

    p_va = pd.DataFrame(
        sigmoid(make_X(meta_va["origin_query"], meta_va["dataset_name"],
                       idf, prior)[0] @ W + b),
        index=meta_va.index, columns=MODELS)
    p_te = pd.DataFrame(
        sigmoid(make_X(meta_te["origin_query"], meta_te["dataset_name"],
                       idf, prior)[0] @ W + b),
        index=meta_te.index, columns=MODELS)

    # Transparent threshold curve on val, then pick t* under the quality floor.
    floor = QUALITY_FLOOR * K_va[MODELS[-1]].mean() * 100
    print(f"train {len(tr)}+{len(aux)} aux | val {len(va)} | test {len(te)} "
          f"(official U1 split, floor={floor:.1f}%)")
    print("\nval threshold curve:")
    best, best_cost = None, np.inf
    for t in np.arange(0.50, 0.96, 0.05):
        m = evaluate(K_va, C_va, L_va, route_cascade(p_va.values, t))
        ok = m["accuracy"] >= floor
        print(f"  t={t:.2f}  acc={m['accuracy']:6.2f}%  cost=${m['avg_cost']:.6f}  "
              f"{'OK' if ok else '--'}")
        if ok and m["avg_cost"] < best_cost:
            best, best_cost = float(t), m["avg_cost"]
    if best is None:
        best = 0.95
    t_star = best

    rows = [
        ("always-strongest", evaluate(K_te, C_te, L_te,
                                      np.full(len(te), len(MODELS) - 1))),
        ("always-cheapest", evaluate(K_te, C_te, L_te, np.zeros(len(te), dtype=int))),
        ("oracle (alpha=%.3f)" % ALPHA,
         evaluate(K_te, C_te, L_te,
                  (C_te + ALPHA * L_te).where(K_te.values == 1, np.inf)
                  .values.argmin(axis=1))),
        ("learned cascade (t=%.2f)" % t_star,
         evaluate(K_te, C_te, L_te, route_cascade(p_te.values, t_star))),
    ]
    cost_s = rows[0][1]["avg_cost"]
    acc_s = rows[0][1]["accuracy"]
    table = pd.DataFrame([
        {
            "policy": name,
            "accuracy_pct": round(m["accuracy"], 2),
            "quality_vs_strongest_pct": round(m["accuracy"] / acc_s * 100, 1),
            "avg_cost_per_query": round(m["avg_cost"], 6),
            "avg_latency_s": round(m["avg_latency"], 3),
            "cost_reduction_vs_strongest_pct": round((1 - m["avg_cost"] / cost_s) * 100, 1),
        }
        for name, m in rows
    ])
    table.to_csv(RESULTS_DIR / "learned_router_report.csv", index=False)

    print(f"\ntuned threshold t* = {t_star:.2f}")
    print(table.to_string(index=False))

    sel = pd.Series([MODELS[i] for i in route_cascade(p_te.values, t_star)]).value_counts()
    print("\nmodel selection distribution (test):")
    print(sel.to_string())


if __name__ == "__main__":
    main()
