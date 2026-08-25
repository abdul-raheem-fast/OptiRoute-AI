import csv
import glob
import os
import sys

# Increase field size limit
for limit in [2**31 - 1, 100000000, 10000000]:
    try:
        csv.field_size_limit(limit)
        break
    except OverflowError:
        pass

source_dir = r"c:\Users\Abdul Raheem\Desktop\New folder"
output_dir = os.path.join(source_dir, "cleaned")

expected_fields = [
    'index', 'dataset_name', 'model_name', 'origin_query', 'prompt',
    'ground_truth', 'prediction', 'score', 'correct', 'prompt_tokens',
    'completion_tokens', 'total_tokens', 'cost', 'estimated_latency',
    'raw_output'
]

def validate():
    errors = []
    
    # 1. Check directories
    for sub in ["individual", "aligned_7_models", "aligned_8_models"]:
        path = os.path.join(output_dir, sub)
        if not os.path.isdir(path):
            errors.append(f"Directory missing: {path}")
            
    if errors:
        print("Initial validation failed:")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)
        
    # 2. Check individual files
    indiv_path = os.path.join(output_dir, "individual")
    indiv_files = glob.glob(os.path.join(indiv_path, "*.csv"))
    if len(indiv_files) != 8:
        errors.append(f"Expected 8 files in individual/, found {len(indiv_files)}")
        
    for f in indiv_files:
        name = os.path.basename(f)
        with open(f, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            headers = next(reader, None)
            
            # Check fields
            if headers != expected_fields:
                errors.append(f"Header mismatch in individual/{name}. Expected: {expected_fields}, Found: {headers}")
                
            # Check sequential indices
            reader_dict = csv.DictReader(file, fieldnames=expected_fields)
            row_count = 0
            for idx, row in enumerate(reader_dict, 1):
                row_count += 1
                if row['index'] != str(idx):
                    errors.append(f"Non-sequential index in individual/{name} at row {idx}. Value: {row['index']}")
                    break
        print(f"Validated individual/{name} successfully ({row_count} rows).")
        
    # 3. Check aligned_7_models
    align_7_path = os.path.join(output_dir, "aligned_7_models")
    align_7_files = glob.glob(os.path.join(align_7_path, "*.csv"))
    if len(align_7_files) != 7:
        errors.append(f"Expected 7 files in aligned_7_models/, found {len(align_7_files)}")
        
    # Track queries and datasets for order consistency
    align_7_queries = []
    
    for f in sorted(align_7_files):
        name = os.path.basename(f)
        queries = []
        with open(f, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                queries.append((row['dataset_name'], row['origin_query']))
                
        if len(queries) != 3352:
            errors.append(f"Expected 3352 rows in aligned_7_models/{name}, found {len(queries)}")
            
        if not align_7_queries:
            align_7_queries = queries
        else:
            if queries != align_7_queries:
                errors.append(f"Query order or content mismatch in aligned_7_models/{name}")
        print(f"Validated aligned_7_models/{name} successfully ({len(queries)} rows).")
                
    # 4. Check aligned_8_models
    align_8_path = os.path.join(output_dir, "aligned_8_models")
    align_8_files = glob.glob(os.path.join(align_8_path, "*.csv"))
    if len(align_8_files) != 8:
        errors.append(f"Expected 8 files in aligned_8_models/, found {len(align_8_files)}")
        
    align_8_queries = []
    
    for f in sorted(align_8_files):
        name = os.path.basename(f)
        queries = []
        with open(f, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                queries.append((row['dataset_name'], row['origin_query']))
                
        if len(queries) != 1887:
            errors.append(f"Expected 1887 rows in aligned_8_models/{name}, found {len(queries)}")
            
        if not align_8_queries:
            align_8_queries = queries
        else:
            if queries != align_8_queries:
                errors.append(f"Query order or content mismatch in aligned_8_models/{name}")
        print(f"Validated aligned_8_models/{name} successfully ({len(queries)} rows).")

    # Output validation results
    if errors:
        print("\nValidation FAILED with the following errors:")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)
    else:
        print("\nValidation PASSED! All files are perfectly cleaned and aligned.")

if __name__ == '__main__':
    validate()
