import csv
import os
import glob

csv.field_size_limit(100000000)

source_file = r"D:\Datasets (FYP)\cleaned\aligned_8_models\Qwen3-8B.csv"

print(f"=== INSPECTING ROW BREAKS IN {os.path.basename(source_file)} ===\n")

with open(source_file, mode='r', encoding='utf-8', errors='ignore') as fp:
    lines = fp.readlines()

print(f"Total raw text lines in file: {len(lines)}")

# Parse with csv reader
with open(source_file, mode='r', encoding='utf-8', errors='ignore') as fp:
    reader = csv.DictReader(fp)
    rows = list(reader)

print(f"Total parsed CSV records: {len(rows)}")
print(f"Line count vs CSV record count difference: {len(lines) - len(rows)} multiline breaks!\n")

# Check rows where raw_output or prediction contains newlines
multiline_count = 0
for idx, r in enumerate(rows, start=1):
    pred = r.get('prediction', '')
    raw = r.get('raw_output', '')
    if '\n' in pred or '\n' in raw or '\r' in pred or '\r' in raw:
        multiline_count += 1
        if multiline_count <= 5:
            print(f"Record #{idx} (index {r.get('index')}) contains newlines:")
            print(f"  dataset_name: {r.get('dataset_name')}")
            print(f"  model_name: {r.get('model_name')}")
            print(f"  raw_output snippet (first 150 chars): {repr(raw[:150])}")
            print()

print(f"Total records with multiline newlines inside text fields: {multiline_count}")
