import glob
import csv
import os
import math

csv.field_size_limit(100000000)

target_dirs = [
    r"D:\AetherFlow\cleaned\aligned_8_models",
    r"D:\AetherFlow\cleaned\aligned_7_models",
    r"D:\AetherFlow\cleaned\individual"
]

print("=== THOROUGH AUDIT OF UPDATED CSV FILES FOR JUNK / ERRORED DATA ===\n")

for t_dir in target_dirs:
    dir_name = os.path.basename(t_dir)
    print(f"=================================================================")
    print(f"AUDITING FOLDER: {dir_name}")
    print(f"=================================================================")
    
    csv_files = sorted(glob.glob(os.path.join(t_dir, '*.csv')))
    
    for f_path in csv_files:
        fname = os.path.basename(f_path)
        
        empty_pred = 0
        empty_raw = 0
        empty_dataset = 0
        invalid_score = 0
        unexpected_datasets = set()
        total_rows = 0
        corrupt_rows = 0
        
        expected_classes = {
            'Coding', 'Mathematical Reasoning', 'Scientific Questionnaire',
            'General Knowledge', 'Competitive Math'
        }
        
        with open(f_path, mode='r', encoding='utf-8', errors='ignore') as fp:
            reader = csv.DictReader(fp)
            fieldnames = reader.fieldnames
            
            for row_idx, r in enumerate(reader, start=2):
                total_rows += 1
                
                # Check for empty critical fields
                pred = str(r.get('prediction', '')).strip()
                raw = str(r.get('raw_output', '')).strip()
                ds = str(r.get('dataset_name', '')).strip()
                score_str = str(r.get('score', '')).strip()
                
                if not pred:
                    empty_pred += 1
                if not raw:
                    empty_raw += 1
                if not ds:
                    empty_dataset += 1
                
                # Check dataset names
                if ds not in expected_classes:
                    unexpected_datasets.add(ds)
                    
                # Check numeric score
                try:
                    score_val = float(score_str)
                    if math.isnan(score_val):
                        invalid_score += 1
                except ValueError:
                    invalid_score += 1
                    
        print(f"File: {fname:<25} | Total Rows: {total_rows}")
        print(f"  Fieldnames: {fieldnames}")
        print(f"  Empty Predictions: {empty_pred} | Empty Raw Outputs: {empty_raw} | Empty Datasets: {empty_dataset}")
        print(f"  Invalid/NaN Scores: {invalid_score}")
        print(f"  Unique Dataset Classes ({len(unexpected_datasets | (expected_classes & set(unexpected_datasets)))}): {sorted(list(set(unexpected_datasets)))}")
        if unexpected_datasets:
            print(f"  ⚠️ Non-standard dataset names found: {sorted(list(unexpected_datasets))}")
        print()

