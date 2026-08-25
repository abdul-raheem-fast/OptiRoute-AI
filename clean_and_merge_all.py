import glob
import csv
import os

csv.field_size_limit(100000000)

full_mapping = {
    # Coding
    "livecodebench": "Coding",
    "arenahard_coding": "Coding",
    "humaneval": "Coding",
    "mbpp": "Coding",
    "swe-bench": "Coding",
    
    # Mathematical Reasoning
    "livemathbench": "Mathematical Reasoning",
    "arenahard_math": "Mathematical Reasoning",
    "math500": "Mathematical Reasoning",
    "mathbench": "Mathematical Reasoning",
    
    # Scientific Questionnaire
    "gpqa": "Scientific Questionnaire",
    "finqa": "Scientific Questionnaire",
    "medqa": "Scientific Questionnaire",
    
    # General Knowledge
    "mmlupro": "General Knowledge",
    "arenahard": "General Knowledge",
    "arenahard_creative_writing": "General Knowledge",
    "arcc": "General Knowledge",
    "bbh": "General Knowledge",
    "winogrande": "General Knowledge",
    "meld": "General Knowledge",
    "emorynlp": "General Knowledge",
    "korbench": "General Knowledge",
    "kandk": "General Knowledge",
    "simpleqa": "General Knowledge",
    "arc-agi": "General Knowledge",
    "hle": "General Knowledge",
    
    # Competitive Math
    "aime": "Competitive Math",
    
    # Pre-existing handles
    "Scientific Questionaire": "Scientific Questionnaire",
    "Complex Coding": "Coding",
    "Complex Math": "Mathematical Reasoning",
    "Creative Writing": "General Knowledge",
    "Complex Prompts": "General Knowledge"
}

target_dirs = [
    r"D:\AetherFlow\cleaned\aligned_8_models",
    r"D:\AetherFlow\cleaned\aligned_7_models",
    r"D:\AetherFlow\cleaned\individual"
]

print("=== APPLYING FULL UNIFIED 5-CLASS MAPPING ACROSS ALL FOLDERS ===\n")

for t_dir in target_dirs:
    dir_name = os.path.basename(t_dir)
    csv_files = sorted(glob.glob(os.path.join(t_dir, '*.csv')))
    print(f"Updating folder: {dir_name} ({len(csv_files)} files)...")
    
    for f_path in csv_files:
        fname = os.path.basename(f_path)
        rows = []
        with open(f_path, mode='r', encoding='utf-8', errors='ignore') as fp:
            reader = csv.DictReader(fp)
            fieldnames = reader.fieldnames
            for r in reader:
                ds = r['dataset_name'].strip()
                if ds in full_mapping:
                    r['dataset_name'] = full_mapping[ds]
                rows.append(r)
                
        with open(f_path, mode='w', encoding='utf-8', newline='') as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            
        print(f"  [x] Updated {fname}")

print("\n=== VERIFYING FINAL UNIQUE CLASSES PER FOLDER ===")
for t_dir in target_dirs:
    dir_name = os.path.basename(t_dir)
    csv_files = sorted(glob.glob(os.path.join(t_dir, '*.csv')))
    all_classes = set()
    for f in csv_files:
        with open(f, mode='r', encoding='utf-8', errors='ignore') as fp:
            reader = csv.DictReader(fp)
            for r in reader:
                all_classes.add(r['dataset_name'])
    print(f"Folder: {dir_name:<20} | Total Classes: {len(all_classes)}")
    print(f"  Classes: {sorted(list(all_classes))}")
    print()
