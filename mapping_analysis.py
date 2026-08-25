import glob
import csv
import os

csv.field_size_limit(100000000)
source_dir = r"D:\AetherFlow\cleaned\individual"
files = glob.glob(os.path.join(source_dir, "*.csv"))

dataset_info = {}

for f in files:
    m = os.path.basename(f).replace('.csv', '')
    with open(f, mode='r', encoding='utf-8', errors='ignore') as fp:
        reader = csv.DictReader(fp)
        for r in reader:
            ds = r['dataset_name'].strip()
            score = float(r.get('score', 0.0))
            if ds not in dataset_info:
                dataset_info[ds] = {'total_rows': 0, 'models': set(), 'scores': []}
            dataset_info[ds]['total_rows'] += 1
            dataset_info[ds]['models'].add(m)
            dataset_info[ds]['scores'].append(score)

print(f"Total Datasets Found: {len(dataset_info)}\n")
print(f"{'Dataset Name':<30} | {'Models':<6} | {'Total Rows':<10} | {'Mean Acc (%)':<12}")
print('-' * 65)

sorted_ds = sorted(dataset_info.keys())
for ds in sorted_ds:
    info = dataset_info[ds]
    mean_acc = (sum(info['scores']) / len(info['scores'])) * 100.0
    print(f"{ds:<30} | {len(info['models']):<6} | {info['total_rows']:<10} | {mean_acc:12.2f}")
