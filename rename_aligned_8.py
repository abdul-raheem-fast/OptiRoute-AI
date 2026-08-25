import glob
import csv
import os

csv.field_size_limit(100000000)

target_dirs = [
    r"D:\Datasets (FYP)\cleaned\aligned_8_models",
    r"D:\Datasets (FYP)\cleaned\aligned_7_models",
    r"D:\Datasets (FYP)\cleaned\individual"
]

rename_map = {
    'livecodebench': 'Coding',
    'livemathbench': 'Mathematical Reasoning',
    'gpqa': 'Scientific Questionaire',
    'mmlupro': 'General Knowledge',
    'aime': 'Competitive Math'
}

for t_dir in target_dirs:
    if not os.path.exists(t_dir):
        continue
    csv_files = glob.glob(os.path.join(t_dir, '*.csv'))
    print(f"Updating dataset names in {os.path.basename(t_dir)} ({len(csv_files)} files)...")

    for f_path in sorted(csv_files):
        name = os.path.basename(f_path)
        rows = []
        with open(f_path, mode='r', encoding='utf-8', errors='ignore') as fp:
            reader = csv.DictReader(fp)
            fieldnames = reader.fieldnames
            for r in reader:
                old_name = r['dataset_name'].strip()
                if old_name in rename_map:
                    r['dataset_name'] = rename_map[old_name]
                rows.append(r)
                
        with open(f_path, mode='w', encoding='utf-8', newline='') as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            
        print(f"  Updated {name}")

print("\nVerification check on updated dataset_name values in aligned_8_models:")
aligned_8_files = sorted(glob.glob(os.path.join(target_dirs[0], '*.csv')))
for f_path in aligned_8_files:
    name = os.path.basename(f_path)
    unique_ds = set()
    with open(f_path, mode='r', encoding='utf-8', errors='ignore') as fp:
        reader = csv.DictReader(fp)
        for r in reader:
            unique_ds.add(r['dataset_name'])
    print(f"  {name}: {sorted(list(unique_ds))}")
