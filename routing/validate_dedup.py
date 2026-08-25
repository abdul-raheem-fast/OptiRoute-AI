"""Task U2: verify the aligned_7 dedup audit produced by build_matrix (A1).

Checks, per model file in cleaned/aligned_7_models:
  1. row count / unique query_id count / duplicate row count match the
     documented quirk (3,352 rows, 3,106 unique, 246 duplicates);
  2. the duplicate query_id SET is identical across all 7 files (alignment);
  3. duplicated rows are true repeats: same dataset_name and origin_query,
     and within one file the repeated rows carry identical model outcomes.

Exits non-zero on any mismatch so it can gate CI / PR reviews.
"""
import csv
import sys
from collections import Counter

from routing.config import ALIGNED7_DIR, MODELS

csv.field_size_limit(100000000)

EXPECTED_ROWS, EXPECTED_UNIQUE, EXPECTED_DUPS = 3352, 3106, 246


def load(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        return list(csv.DictReader(f))


def main():
    dup_sets, first = {}, None
    errors = []
    for model in MODELS:
        path = ALIGNED7_DIR / f"{model}.csv"
        if not path.exists():
            continue
        rows = load(path)
        ids = [r["query_id"] for r in rows]
        counts = Counter(ids)
        dups = sorted(q for q, n in counts.items() if n > 1)
        dup_sets[model] = dups

        if len(rows) != EXPECTED_ROWS or len(counts) != EXPECTED_UNIQUE \
                or len(dups) != EXPECTED_DUPS:
            errors.append(f"{model}: counts {len(rows)}/{len(counts)}/{len(dups)} "
                          f"!= expected {EXPECTED_ROWS}/{EXPECTED_UNIQUE}/{EXPECTED_DUPS}")

        # duplicated rows must repeat the same query text and outcomes
        by_id = {}
        for r in rows:
            by_id.setdefault(r["query_id"], []).append(r)
        for q in dups:
            texts = {(r["dataset_name"], r["origin_query"], r["prediction"],
                      r["score"]) for r in by_id[q]}
            if len(texts) != 1:
                errors.append(f"{model}: query {q} duplicated with differing content")

        if first is None:
            first = (model, dups)
        elif dups != first[1]:
            errors.append(f"{model}: duplicate id set differs from {first[0]}")

    if errors:
        print("DEDUP VERIFICATION FAILED:")
        for e in errors:
            print(" -", e)
        sys.exit(1)

    print(f"DEDUP VERIFICATION PASSED: {len(dup_sets)} files, "
          f"{EXPECTED_ROWS} rows / {EXPECTED_UNIQUE} unique / {EXPECTED_DUPS} dups each, "
          "identical duplicate-id sets, repeated rows are true repeats.")


if __name__ == "__main__":
    main()
