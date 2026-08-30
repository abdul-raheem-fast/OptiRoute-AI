import csv
import glob
import os
import sys

# Increase field size limit to support large raw_output text
for limit in [2**31 - 1, 100000000, 10000000]:
    try:
        csv.field_size_limit(limit)
        break
    except OverflowError:
        pass

source_dir = r"c:\Users\Abdul Raheem\Desktop\New folder"
output_dir = os.path.join(source_dir, "cleaned")

os.makedirs(os.path.join(output_dir, "individual"), exist_ok=True)
os.makedirs(os.path.join(output_dir, "aligned_7_models"), exist_ok=True)
os.makedirs(os.path.join(output_dir, "aligned_8_models"), exist_ok=True)

csv_files = glob.glob(os.path.join(source_dir, "*.csv"))
print(f"Found {len(csv_files)} source files.")

# Cleaned data cache
# Key: filename, Value: list of cleaned rows (dicts)
cleaned_data = {}

# Statically define target columns to guarantee consistency across all files
all_fields = [
    'index', 'dataset_name', 'model_name', 'origin_query', 'prompt',
    'ground_truth', 'prediction', 'score', 'correct', 'prompt_tokens',
    'completion_tokens', 'total_tokens', 'cost', 'estimated_latency',
    'raw_output'
]

for f_path in csv_files:
    name = os.path.basename(f_path)
    print(f"\nProcessing {name}...")
    
    rows = []
    seen_queries = set()
    dup_count = 0
    error_count = 0
    
    with open(f_path, mode='r', encoding='utf-8', errors='ignore') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        
        # Check if index is in the column name (handling quotes and BOM)
        index_col = None
        for fn in fieldnames:
            if "index" in fn.lower():
                index_col = fn
                break
                
        if not index_col:
            raise ValueError(f"Could not find index column in {name}. Available: {fieldnames}")
            
        for row in reader:
            pred = row.get("prediction", "")
            raw = row.get("raw_output", "")
            
            # Filter out empty/null/whitespace-only predictions or raw outputs
            if not pred or pred.strip() == "" or not raw or raw.strip() == "":
                error_count += 1
                continue
                
            cleaned_row = {}
            
            # Map standard fields
            cleaned_row["index"] = row.get(index_col, "")
            
            # Populate standard columns, fallback to empty string if missing
            for field in all_fields:
                if field == "index":
                    continue
                val = row.get(field, "")
                if val is None or (isinstance(val, str) and val.strip() == ''):
                    val = ""
                cleaned_row[field] = val
                
            # Thorough cleaning of junk values:
            # 1. Strip whitespace from categorical fields
            for fld in ['dataset_name', 'model_name', 'correct', 'score']:
                cleaned_row[fld] = str(cleaned_row[fld]).strip()
                
            # 2. Clean negative or non-numeric values in numeric columns to empty string
            for fld in ['estimated_latency', 'cost', 'prompt_tokens', 'completion_tokens', 'total_tokens']:
                val = cleaned_row[fld]
                if val != "":
                    try:
                        num_val = float(val)
                        if num_val < 0:
                            cleaned_row[fld] = ""
                    except ValueError:
                        cleaned_row[fld] = ""
            
            # Deduplicate check: keep first occurrence of (dataset_name, origin_query)
            ds = cleaned_row.get("dataset_name", "")
            q = cleaned_row.get("origin_query", "")
            key = (ds, q)
            
            if key in seen_queries:
                dup_count += 1
                continue  # Skip duplicate row
            
            seen_queries.add(key)
            rows.append(cleaned_row)
            
    print(f"  Rows read: {len(rows) + dup_count + error_count}")
    print(f"  Duplicates dropped: {dup_count}")
    print(f"  Errors dropped (empty predictions/raw outputs): {error_count}")
    print(f"  Cleaned rows: {len(rows)}")
    cleaned_data[name] = rows
    
    # Save individual cleaned files
    out_path = os.path.join(output_dir, "individual", name)
    with open(out_path, mode='w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=all_fields)
        writer.writeheader()
        # Re-index individual clean rows sequentially
        for idx, row in enumerate(rows, 1):
            row["index"] = str(idx)
            writer.writerow(row)
            
print("\nIndividual files cleaned and saved.")

# --- ALIGNMENT PHASE ---

# Create key-lookup dictionaries for fast matching
# Key: filename, Value: dict of (dataset_name, origin_query) -> row
data_lookups = {}
for name, rows in cleaned_data.items():
    data_lookups[name] = {(r["dataset_name"], r["origin_query"]): r for r in rows}

# 1. Align 7 major models (excluding gpt-4.1.csv)
major_filenames = [name for name in cleaned_data.keys() if "gpt-4.1.csv" not in name]
print(f"\nAligning 7 major files: {major_filenames}")

major_keys_sets = [set(data_lookups[name].keys()) for name in major_filenames]
intersection_keys_7 = set.intersection(*major_keys_sets)
print(f"Common queries in 7 models: {len(intersection_keys_7)}")

# Sort keys to ensure identical row ordering across files
sorted_keys_7 = sorted(list(intersection_keys_7), key=lambda x: (x[0], x[1]))

for name in major_filenames:
    out_path = os.path.join(output_dir, "aligned_7_models", name)
    with open(out_path, mode='w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=all_fields)
        writer.writeheader()
        
        for idx, key in enumerate(sorted_keys_7, 1):
            row = data_lookups[name][key].copy()
            row["index"] = str(idx)  # Sequential indexing
            writer.writerow(row)

print("Aligned 7-model datasets written successfully.")

# 2. Align all 8 models (including gpt-4.1.csv)
all_filenames = list(cleaned_data.keys())
print(f"\nAligning all 8 files: {all_filenames}")

all_keys_sets = [set(data_lookups[name].keys()) for name in all_filenames]
intersection_keys_8 = set.intersection(*all_keys_sets)
print(f"Common queries in all 8 models: {len(intersection_keys_8)}")

# Sort keys to ensure identical row ordering across files
sorted_keys_8 = sorted(list(intersection_keys_8), key=lambda x: (x[0], x[1]))

for name in all_filenames:
    out_path = os.path.join(output_dir, "aligned_8_models", name)
    with open(out_path, mode='w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=all_fields)
        writer.writeheader()
        
        for idx, key in enumerate(sorted_keys_8, 1):
            row = data_lookups[name][key].copy()
            row["index"] = str(idx)  # Sequential indexing
            writer.writerow(row)

print("Aligned 8-model datasets written successfully.")
print("\nDataset cleaning and alignment process completed.")
