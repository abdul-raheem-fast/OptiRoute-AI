"""Task A1: build the query x model routing matrix from aligned_8_models.

Outputs (gitignored, regenerated on demand):
  routing/data/routing_matrix.csv  - long form, one row per (query, model):
                                     query_id, dataset_name, model_name,
                                     correct, cost, latency
  routing/data/query_meta.csv      - one row per query: query_id,
                                     dataset_name, origin_query, n_correct
  routing/data/aligned7_dedup_report.json - duplicate query_id audit of the
                                     extended aligned_7 set (input for U2)

Latency note: the historical Phase 1 CSVs carry estimated_latency; missing
values are filled with the per-model median. run_eval.py output for new
models carries measured actual_latency and can be merged later.
"""
import csv
import json
from collections import Counter

import pandas as pd

from routing.config import ALIGNED7_DIR, ALIGNED8_DIR, MODELS, OUT_DIR

csv.field_size_limit(100000000)


def _load_aligned(directory, model):
    path = directory / f"{model}.csv"
    rows = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def build_matrix():
    """Return the long-form routing matrix as a DataFrame."""
    records = []
    for model in MODELS:
        for r in _load_aligned(ALIGNED8_DIR, model):
            cost = float(r["cost"])
            lat = r["estimated_latency"].strip()
            records.append({
                "query_id": r["query_id"],
                "dataset_name": r["dataset_name"],
                "model_name": model,
                "origin_query": r["origin_query"],
                "correct": int(float(r["correct"])),
                "cost": cost,
                "latency_raw": float(lat) if lat else None,
            })
    df = pd.DataFrame.from_records(records)
    # Fill the occasional missing latency with the per-model median.
    df["latency"] = df.groupby("model_name")["latency_raw"].transform(
        lambda s: s.fillna(s.median())
    )
    return df[["query_id", "dataset_name", "model_name", "origin_query",
               "correct", "cost", "latency"]]


def build_query_meta(matrix):
    """Per-query metadata: class, text, and cross-model agreement count."""
    meta = (matrix.groupby(["query_id", "dataset_name", "origin_query"])
            ["correct"].sum().reset_index().rename(columns={"correct": "n_correct"}))
    return meta


def aligned7_dedup_report():
    """Duplicate query_id audit for the extended aligned_7 set (input for U2)."""
    report = {}
    for model in MODELS:
        path = ALIGNED7_DIR / f"{model}.csv"
        if not path.exists():  # gpt-4.1 is absent from aligned_7
            continue
        ids = [r["query_id"] for r in _load_aligned(ALIGNED7_DIR, model)]
        counts = Counter(ids)
        dups = {qid: n for qid, n in counts.items() if n > 1}
        report[model] = {
            "rows": len(ids),
            "unique_query_ids": len(counts),
            "duplicate_rows": len(ids) - len(counts),
            "duplicate_query_ids": sorted(dups),
        }
    return report


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    matrix = build_matrix()
    matrix.to_csv(OUT_DIR / "routing_matrix.csv", index=False)
    print(f"routing_matrix.csv : {len(matrix)} rows "
          f"({matrix['query_id'].nunique()} queries x {matrix['model_name'].nunique()} models)")

    meta = build_query_meta(matrix)
    meta.to_csv(OUT_DIR / "query_meta.csv", index=False)
    print(f"query_meta.csv     : {len(meta)} queries")
    print("agreement distribution (n_correct of 8):")
    print(meta["n_correct"].value_counts().sort_index().to_string())

    report = aligned7_dedup_report()
    with open(OUT_DIR / "aligned7_dedup_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    first = next(iter(report.values()))
    print(f"aligned7 dedup     : {first['rows']} rows, {first['unique_query_ids']} unique, "
          f"{first['duplicate_rows']} duplicate rows per file")

    # Class balance summary for the record.
    print("queries per class:")
    print(meta["dataset_name"].value_counts().to_string())


if __name__ == "__main__":
    main()
