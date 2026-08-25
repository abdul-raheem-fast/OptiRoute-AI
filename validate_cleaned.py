"""Task A4: repo hygiene - dataset validator for the CURRENT repo layout.

Replaces the stale validator (hardcoded Desktop path, pre-query_id 15-column
schema). Now validates, relative to this file:

  cleaned/individual        8 files, 15 columns (no query_id), sequential index
  cleaned/aligned_7_models  7 files, 16 columns, 3352 rows, identical order
  cleaned/aligned_8_models  8 files, 16 columns, 1887 rows, identical order

Cross-checks: query_id == sha1("<class>.lower()||<query>")[:12] (the scheme
of add_query_ids.py), correct in {0,1}, cost >= 0. Empty ground_truth /
latency cells are reported as WARNINGS (known, documented data caveats),
not errors. Exit code 1 on any error.
"""
import csv
import glob
import hashlib
import os
import sys

csv.field_size_limit(100000000)

ROOT = os.path.dirname(os.path.abspath(__file__))
CLEANED = os.path.join(ROOT, "cleaned")

INDIVIDUAL_FIELDS = [
    'index', 'dataset_name', 'model_name', 'origin_query', 'prompt',
    'ground_truth', 'prediction', 'score', 'correct', 'prompt_tokens',
    'completion_tokens', 'total_tokens', 'cost', 'estimated_latency',
    'raw_output',
]
ALIGNED_FIELDS = [
    'index', 'dataset_name', 'query_id', 'model_name', 'origin_query',
    'prompt', 'ground_truth', 'prediction', 'score', 'correct',
    'prompt_tokens', 'completion_tokens', 'total_tokens', 'cost',
    'estimated_latency', 'raw_output',
]
EXPECTED_COUNTS = {"aligned_7_models": 3352, "aligned_8_models": 1887}
EXPECTED_FILES = {"individual": 8, "aligned_7_models": 7,
                  "aligned_8_models": 8}


def make_qid(dataset_name, origin_query):
    basis = f"{dataset_name.strip().lower()}||{origin_query.strip()}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def validate():
    errors, warnings = [], []

    for sub, n_files in EXPECTED_FILES.items():
        path = os.path.join(CLEANED, sub)
        if not os.path.isdir(path):
            errors.append(f"Directory missing: {path}")
            continue
        found = glob.glob(os.path.join(path, "*.csv"))
        if len(found) != n_files:
            errors.append(f"{sub}/: expected {n_files} csv files, "
                          f"found {len(found)}")

    if errors:
        _fail(errors, warnings)

    # ------------------------------------------------ individual (15 cols)
    for f in sorted(glob.glob(os.path.join(CLEANED, "individual", "*.csv"))):
        name = os.path.basename(f)
        with open(f, encoding="utf-8", errors="ignore", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames != INDIVIDUAL_FIELDS:
                errors.append(f"individual/{name}: header mismatch: "
                              f"{reader.fieldnames}")
                continue
            rows = 0
            for i, row in enumerate(reader, 1):
                rows += 1
                if row['index'] != str(i):
                    errors.append(f"individual/{name}: non-sequential index "
                                  f"at row {i} (got {row['index']})")
                    break
                if row['correct'] not in ('0', '1'):
                    errors.append(f"individual/{name}: bad correct "
                                  f"value at row {i}")
                    break
        print(f"OK individual/{name} ({rows} rows)")

    # ------------------------------------------- aligned 7/8 (16 cols each)
    for sub in ["aligned_7_models", "aligned_8_models"]:
        ref_order = None
        for f in sorted(glob.glob(os.path.join(CLEANED, sub, "*.csv"))):
            name = os.path.basename(f)
            order, rows, bad_qid, empty_gt, empty_lat = [], 0, 0, 0, 0
            with open(f, encoding="utf-8", errors="ignore", newline="") as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames != ALIGNED_FIELDS:
                    errors.append(f"{sub}/{name}: header mismatch: "
                                  f"{reader.fieldnames}")
                    continue
                for row in reader:
                    rows += 1
                    order.append((row['dataset_name'], row['origin_query'],
                                  row['query_id']))
                    if row['query_id'] != make_qid(row['dataset_name'],
                                                   row['origin_query']):
                        bad_qid += 1
                    if row['correct'] not in ('0', '1'):
                        errors.append(f"{sub}/{name}: bad correct at "
                                      f"row {rows}")
                    try:
                        if float(row['cost']) < 0:
                            errors.append(f"{sub}/{name}: negative cost at "
                                          f"row {rows}")
                    except ValueError:
                        errors.append(f"{sub}/{name}: non-numeric cost at "
                                      f"row {rows}")
                    if not row['ground_truth'].strip():
                        empty_gt += 1
                    if not row['estimated_latency'].strip():
                        empty_lat += 1

            if rows != EXPECTED_COUNTS[sub]:
                errors.append(f"{sub}/{name}: expected "
                              f"{EXPECTED_COUNTS[sub]} rows, found {rows}")
            if bad_qid:
                errors.append(f"{sub}/{name}: {bad_qid} query_ids do not "
                              f"match the sha1 scheme")
            if ref_order is None:
                ref_order = order
            elif order != ref_order:
                errors.append(f"{sub}/{name}: query order/content differs "
                              f"from first file")
            if empty_gt:
                warnings.append(f"{sub}/{name}: {empty_gt} empty "
                                f"ground_truth cells")
            if empty_lat:
                warnings.append(f"{sub}/{name}: {empty_lat} empty "
                                f"estimated_latency cells")
            print(f"OK {sub}/{name} ({rows} rows)")

    _fail(errors, warnings)


def _fail(errors, warnings):
    for w in warnings:
        print(f"WARNING: {w}")
    if errors:
        print("\nValidation FAILED:")
        for e in errors:
            print(f" - {e}")
        sys.exit(1)
    print("\nValidation PASSED! All files are perfectly cleaned and aligned.")


if __name__ == '__main__':
    validate()
