"""Task R3: publication figures for the routing comparison.

Reads only reproducible artifacts produced by routing/baselines.py
(baselines_report.csv, threshold_curves.csv, policy_choices.npz) plus the
official U1 splits, and renders four figures into routing/results/figures/:

  1 policy_comparison.png   accuracy and cost per policy, test split
  2 cost_accuracy_frontier.png  cost/accuracy scatter with the quality floor
  3 tier_breakdown.png      accuracy per difficulty tier (RQ4), key policies
  4 threshold_curves.png    val accuracy/cost vs cascade threshold t, t* marked
"""
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from routing.config import QUALITY_FLOOR, RESULTS_DIR
from routing.metrics import breakdown
from routing.oracle import load_wide
from routing.splits import load_splits

FIG_DIR = RESULTS_DIR / "figures"

KEY_POLICIES = ["always-strongest", "always-cheapest", "class-based",
                "knn-cascade", "learned-cascade", "oracle"]


def _match(npz_keys, prefix):
    for k in npz_keys:
        if k == prefix or k.startswith(prefix + "_t"):
            return k
    if prefix in npz_keys:
        return prefix
    raise KeyError(prefix)


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    rep = pd.read_csv(RESULTS_DIR / "baselines_report.csv")
    curves = pd.read_csv(RESULTS_DIR / "threshold_curves.csv")
    npz = np.load(RESULTS_DIR / "policy_choices.npz", allow_pickle=True)
    qids = list(npz["test_qids"])

    _, _, _, tier_map = load_splits()
    K, _, _ = load_wide()
    K_te = K.loc[qids]
    te_df = pd.DataFrame({"query_id": qids,
                          "tier": [tier_map[q] for q in qids]})

    acc_s = rep.loc[rep["policy"] == "always-strongest", "accuracy_pct"].iloc[0]
    floor = QUALITY_FLOOR * acc_s

    # ------------------------------------------- 1. policy comparison bars
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
    y = np.arange(len(rep))
    colors = ["#2ca02c" if m else "#7f7f7f" for m in rep["meets_quality_floor"]]
    colors = ["#ffbf0e" if p == "oracle" else c
              for p, c in zip(rep["policy"], colors)]
    ax1.barh(y, rep["accuracy_pct"], color=colors)
    ax1.axvline(floor, ls="--", c="crimson", lw=1)
    ax1.set_xlabel("accuracy on test (%)")
    ax1.set_title(f"accuracy (floor = {floor:.1f}%)")
    ax2.barh(y, rep["avg_cost_per_query"], color=colors)
    ax2.set_xscale("log")
    ax2.set_xlabel("avg cost per query (USD, log)")
    ax2.set_title("cost")
    ax1.set_yticks(y)
    ax1.set_yticklabels(rep["policy"])
    ax1.invert_yaxis()
    fig.suptitle("Routing policies on the official test split (n=%d)" % len(qids))
    fig.tight_layout()
    fig.savefig(FIG_DIR / "policy_comparison.png", dpi=150)
    plt.close(fig)

    # ------------------------------------------- 2. cost/accuracy frontier
    fig, ax = plt.subplots(figsize=(9, 6))
    for _, r in rep.iterrows():
        marker, size = ("*", 350) if r["policy"] == "oracle" else ("o", 90)
        ax.scatter(r["avg_cost_per_query"], r["accuracy_pct"],
                   s=size, marker=marker, zorder=3,
                   c="#ffbf0e" if r["policy"] == "oracle"
                   else ("#2ca02c" if r["meets_quality_floor"] else "#7f7f7f"),
                   edgecolors="k", linewidths=0.6)
        ax.annotate(r["policy"], (r["avg_cost_per_query"], r["accuracy_pct"]),
                    xytext=(7, 5), textcoords="offset points", fontsize=8)
    ax.axhline(floor, ls="--", c="crimson", lw=1)
    ax.text(ax.get_xlim()[0], floor, f" quality floor ({floor:.1f}%)",
            color="crimson", va="bottom", fontsize=8)
    ax.set_xscale("log")
    ax.set_xlabel("avg cost per query (USD, log)")
    ax.set_ylabel("accuracy on test (%)")
    ax.set_title("Cost-accuracy frontier (star = hindsight oracle)")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "cost_accuracy_frontier.png", dpi=150)
    plt.close(fig)

    # ------------------------------------------- 3. tier breakdown (RQ4)
    chosen = {}
    for prefix in KEY_POLICIES:
        key = _match(list(npz.files), prefix.replace("-", "_"))
        label = prefix
        for p in rep["policy"]:
            if p.replace("-", "_").startswith(prefix.replace("-", "_")) \
                    and p != prefix:
                label = p
        chosen[label] = npz[key]
    tiers = ["easy", "medium", "hard"]
    bd = {name: breakdown(K_te, ch, te_df, by="tier")
          .set_index("tier")["accuracy_pct"] for name, ch in chosen.items()}
    bd = pd.DataFrame(bd).reindex(tiers)

    fig, ax = plt.subplots(figsize=(11, 5.5))
    x = np.arange(len(tiers))
    w = 0.8 / len(bd.columns)
    for i, col in enumerate(bd.columns):
        ax.bar(x + i * w, bd[col], w, label=col)
    ax.set_xticks(x + 0.4 - w / 2)
    ax.set_xticklabels(tiers)
    ax.set_ylabel("accuracy on test (%)")
    ax.set_title("Accuracy by difficulty tier (U3) - RQ4")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "tier_breakdown.png", dpi=150)
    plt.close(fig)

    # ------------------------------------------- 4. threshold curves + t*
    t_stars = {}
    for p in rep["policy"]:
        m = re.search(r"\(t=([0-9.]+)\)", p)
        if m:
            t_stars[p.split(" (")[0]] = float(m.group(1))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), sharey=False)
    for name, g in curves.groupby("policy"):
        ax1.plot(g["t"], g["val_accuracy_pct"], "-o", ms=3, label=name)
        ax2.plot(g["t"], g["val_avg_cost"], "-o", ms=3, label=name)
        if name in t_stars:
            for ax in (ax1, ax2):
                ax.axvline(t_stars[name], ls=":", alpha=0.5)
    ax1.axhline(floor, ls="--", c="crimson", lw=1)
    ax1.set_ylabel("val accuracy (%)")
    ax1.set_title("accuracy vs threshold (floor dashed)")
    ax2.set_xlabel("cascade threshold t")
    ax2.set_ylabel("val avg cost (USD)")
    ax2.set_title("cost vs threshold (dotted = t*)")
    ax1.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "threshold_curves.png", dpi=150)
    plt.close(fig)

    print("figures written to", FIG_DIR)
    for f in sorted(FIG_DIR.glob("*.png")):
        print("  ", f.name)


if __name__ == "__main__":
    main()
