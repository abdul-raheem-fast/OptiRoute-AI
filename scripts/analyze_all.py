import glob
import csv
import os
import math

csv.field_size_limit(100000000)

source_dir = r"D:\AetherFlow\cleaned\individual"
csv_files = sorted(glob.glob(os.path.join(source_dir, "*.csv")))

models = [os.path.basename(f).replace('.csv', '') for f in csv_files]
data = {m: {} for m in models}

for f, m in zip(csv_files, models):
    with open(f, mode='r', encoding='utf-8') as fp:
        reader = csv.DictReader(fp)
        for r in reader:
            ds = r['dataset_name'].strip()
            score = float(r.get('score', 0.0))
            if ds not in data[m]:
                data[m][ds] = []
            data[m][ds].append(score)

all_datasets = set()
for m in models:
    all_datasets.update(data[m].keys())

print("=== ALL BENCHMARK DATASETS RANKED BY MEAN ACCURACY ACROSS MODELS ===\n")

results = []
for ds in sorted(all_datasets):
    accs = []
    for m in models:
        if ds in data[m]:
            scores = data[m][ds]
            mean_m = (sum(scores) / len(scores)) * 100.0 if scores else 0.0
            accs.append(mean_m)
    overall_mean = sum(accs) / len(accs) if accs else 0.0
    results.append({
        'ds': ds,
        'mean': overall_mean,
        'min': min(accs) if accs else 0.0,
        'max': max(accs) if accs else 0.0,
        'models_eval': len(accs)
    })

results.sort(key=lambda x: x['mean'], reverse=True)

print(f"{'Dataset Name':<30} | {'Models':<6} | {'Mean Acc (%)':<12} | {'Range (%)':<18}")
print('-' * 75)
for r in results:
    print(f"{r['ds']:<30} | {r['models_eval']:<6} | {r['mean']:12.2f} | [{r['min']:5.2f} - {r['max']:5.2f}]")
