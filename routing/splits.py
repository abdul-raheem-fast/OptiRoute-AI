"""Tasks U1 + U3: official stratified splits and difficulty tiers.

Difficulty tiers (U3) are derived from cross-model agreement on the aligned_8
ground truth - the number of the 8 models that answer a query correctly:

    easy   : 6-8 models correct
    medium : 3-5 models correct
    hard   : 0-2 models correct

This is a label-free, reproducible proxy that connects directly to the
routing-collapse / routing-plateau literature (RQ4).

Splits (U1) are 70/15/15 stratified by (capability class x difficulty tier),
seeded for reproducibility. Outputs (gitignored, regenerated on demand):

    routing/data/splits.csv          - query_id, dataset_name, tier, split
    routing/data/splits_manifest.json- seed, thresholds, per-stratum counts

The leakage audit verifies (a) splits are disjoint and complete, and
(b) no aligned_7 duplicate query id can leak: any query id that appears in
val/test is excluded from auxiliary training use (enforced by the routers).
"""
import json

import numpy as np
import pandas as pd

from routing.config import OUT_DIR, SEED

TIER_RULES = [("easy", 6, 8), ("medium", 3, 5), ("hard", 0, 2)]
SPLIT_FRACS = {"train": 0.70, "val": 0.15, "test": 0.15}


def tier_of(n_correct):
    for name, lo, hi in TIER_RULES:
        if lo <= n_correct <= hi:
            return name
    raise ValueError(f"n_correct out of range: {n_correct}")


def build_splits():
    """Return the splits DataFrame (query_id, dataset_name, tier, split)."""
    meta = pd.read_csv(OUT_DIR / "query_meta.csv")
    meta = meta.drop_duplicates("query_id")
    meta["tier"] = meta["n_correct"].map(tier_of)

    rng = np.random.default_rng(SEED)
    splits = []
    for (cls, tier), grp in meta.groupby(["dataset_name", "tier"]):
        idx = grp["query_id"].to_numpy()
        rng.shuffle(idx)
        n = len(idx)
        n_tr = int(round(SPLIT_FRACS["train"] * n))
        n_va = int(round(SPLIT_FRACS["val"] * n))
        # keep at least 1 test row for every non-empty stratum
        if n >= 1 and n_tr + n_va >= n:
            n_va = max(0, n - n_tr - 1)
        for qid, split in (
            [(q, "train") for q in idx[:n_tr]]
            + [(q, "val") for q in idx[n_tr:n_tr + n_va]]
            + [(q, "test") for q in idx[n_tr + n_va:]]
        ):
            splits.append((qid, cls, tier, split))
    out = pd.DataFrame(splits, columns=["query_id", "dataset_name", "tier", "split"])
    return out.sort_values("query_id").reset_index(drop=True)


def leakage_audit(splits):
    """Disjointness/completeness + aligned_7 duplicate cross-check."""
    dup = splits["query_id"].duplicated().sum()
    assert dup == 0, f"{dup} query ids appear in more than one split"
    counts = splits["split"].value_counts()
    meta = pd.read_csv(OUT_DIR / "query_meta.csv").drop_duplicates("query_id")
    assert set(splits["query_id"]) == set(meta["query_id"]), "split != full query set"

    with open(OUT_DIR / "aligned7_dedup_report.json", encoding="utf-8") as f:
        report = json.load(f)
    dup_ids = set(next(iter(report.values()))["duplicate_query_ids"])
    val_test = set(splits.loc[splits["split"] != "train", "query_id"])
    leaked = dup_ids & val_test
    return {
        "queries": len(splits),
        "split_counts": counts.to_dict(),
        "aligned7_duplicate_ids": len(dup_ids),
        "duplicate_ids_in_val_or_test": sorted(leaked),
        "note": "routers must exclude these ids from aux training data",
    }


def load_splits():
    """Convenience loader: returns (tr, va, te) query-id lists + tier map."""
    df = pd.read_csv(OUT_DIR / "splits.csv")
    get = lambda s: df.loc[df["split"] == s, "query_id"].tolist()
    return get("train"), get("val"), get("test"), dict(zip(df["query_id"], df["tier"]))


def main():
    splits = build_splits()
    splits.to_csv(OUT_DIR / "splits.csv", index=False)

    manifest = {
        "seed": SEED,
        "fracs": SPLIT_FRACS,
        "tier_rules": {name: [lo, hi] for name, lo, hi in TIER_RULES},
        "strata": {
            f"{cls} | {tier}": g["split"].value_counts().to_dict()
            for (cls, tier), g in splits.groupby(["dataset_name", "tier"])
        },
    }
    manifest.update(leakage_audit(splits))
    with open(OUT_DIR / "splits_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("tier distribution:")
    print(splits["tier"].value_counts().to_string())
    print("\nsplit sizes:", manifest["split_counts"])
    print("\nstratum counts (class | tier -> train/val/test):")
    for k, v in manifest["strata"].items():
        print(f"  {k:<38} {v}")
    print(f"\naligned_7 duplicate ids: {manifest['aligned7_duplicate_ids']}, "
          f"in val/test: {len(manifest['duplicate_ids_in_val_or_test'])} "
          f"(routers exclude them from aux data)")


if __name__ == "__main__":
    main()
