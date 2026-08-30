import csv
import hashlib
import glob
import os

csv.field_size_limit(100000000)

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET_DIRS = [
    os.path.join(ROOT, "cleaned", "aligned_8_models"),
    os.path.join(ROOT, "cleaned", "aligned_7_models"),
]


def make_qid(dataset_name, origin_query):
    basis = f"{dataset_name.strip().lower()}||{origin_query.strip()}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def process_file(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        rows = list(reader)

    if "query_id" in fields:
        print(f"SKIP (already has query_id): {path}")
        return

    insert_at = fields.index("dataset_name") + 1 if "dataset_name" in fields else 0
    new_fields = fields[:insert_at] + ["query_id"] + fields[insert_at:]

    seen = {}
    collisions = 0
    for r in rows:
        qid = make_qid(r.get("dataset_name", ""), r.get("origin_query", ""))
        if qid in seen and seen[qid] != r.get("origin_query"):
            collisions += 1
        seen[qid] = r.get("origin_query")
        r["query_id"] = qid

    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=new_fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)
    print(f"OK  {len(rows)} rows, {len(seen)} unique query_ids -> {os.path.basename(path)}  (collisions: {collisions})")


def main():
    files = []
    for d in TARGET_DIRS:
        files.extend(sorted(glob.glob(os.path.join(d, "*.csv"))))
    if not files:
        print("No CSVs found to update.")
        return
    print(f"Processing {len(files)} files...\n")
    for p in files:
        process_file(p)
    print("\nDone. Verify with validate_cleaned.py or by opening a file in Excel.")


if __name__ == "__main__":
    main()
