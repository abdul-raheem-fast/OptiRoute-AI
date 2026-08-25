import glob
import csv
import os

csv.field_size_limit(100000000)

target_dirs = [
    r"D:\AetherFlow\cleaned\aligned_8_models",
    r"D:\AetherFlow\cleaned\aligned_7_models",
    r"D:\AetherFlow\cleaned\individual"
]

print("=== CHECKING FOR ANY MALFORMED ROWS OR UNMAPPED DATASET NAMES ===\n")

for t_dir in target_dirs:
    dir_name = os.path.basename(t_dir)
    csv_files = sorted(glob.glob(os.path.join(t_dir, '*.csv')))
    print(f"Directory: {dir_name}")
    
    for f in csv_files:
        fname = os.path.basename(f)
        ds_counts = {}
        row_count = 0
        corrupt_rows = []
        
        with open(f, mode='r', encoding='utf-8', errors='ignore') as fp:
            reader = csv.DictReader(fp)
            for idx, r in enumerate(reader, start=2):
                row_count += 1
                ds = r.get('dataset_name', '').strip()
                ds_counts[ds] = ds_counts.get(ds, 0) + 1
                
                # Check for structural corruptions (missing keys or misplaced columns)
                if None in r or len(r) != 15:
                    corrupt_rows.append(idx)
                    
        print(f"  {fname:<25} | Rows: {row_count:<6} | Corrupt Rows: {len(corrupt_rows)}")
        print(f"     Dataset Classes ({len(ds_counts)}): {sorted(list(ds_counts.keys()))}")
    print()
