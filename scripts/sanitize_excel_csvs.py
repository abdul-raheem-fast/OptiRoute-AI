import glob
import csv
import os

csv.field_size_limit(100000000)

target_dirs = [
    r"D:\AetherFlow\cleaned\aligned_8_models",
    r"D:\AetherFlow\cleaned\aligned_7_models",
    r"D:\AetherFlow\cleaned\individual"
]

print("=== SANITIZING RAW LINE BREAKS IN TEXT FIELDS FOR PERFECT EXCEL DISPLAY ===\n")

for t_dir in target_dirs:
    dir_name = os.path.basename(t_dir)
    csv_files = sorted(glob.glob(os.path.join(t_dir, '*.csv')))
    print(f"Sanitizing folder: {dir_name} ({len(csv_files)} files)...")
    
    for f_path in csv_files:
        fname = os.path.basename(f_path)
        rows = []
        replaced_newlines = 0
        
        with open(f_path, mode='r', encoding='utf-8', errors='ignore') as fp:
            reader = csv.DictReader(fp)
            fieldnames = reader.fieldnames
            
            for r in reader:
                for col in fieldnames:
                    val = r.get(col, '')
                    if isinstance(val, str) and ('\n' in val or '\r' in val):
                        # Replace raw line breaks with a single space to prevent Excel row wrapping
                        new_val = val.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
                        r[col] = new_val
                        replaced_newlines += 1
                rows.append(r)
                
        with open(f_path, mode='w', encoding='utf-8', newline='') as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(rows)
            
        print(f"  [x] Sanitized {fname:<25} | Line breaks cleaned: {replaced_newlines}")

print("\nSanitization completed! All CSV files now display perfectly on 1 line per record in Excel.")
