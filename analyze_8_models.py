import glob
import csv
import os
import math

csv.field_size_limit(100000000)

source_dir = r"D:\AetherFlow\cleaned\aligned_8_models"
csv_files = sorted(glob.glob(os.path.join(source_dir, "*.csv")))

models = [os.path.basename(f).replace('.csv', '') for f in csv_files]
data = {m: {} for m in models}
dataset_counts = {}

for f, m in zip(csv_files, models):
    with open(f, mode='r', encoding='utf-8') as fp:
        reader = csv.DictReader(fp)
        for r in reader:
            ds = r['dataset_name'].strip()
            score = float(r.get('score', 0.0))
            if ds not in data[m]:
                data[m][ds] = []
            data[m][ds].append(score)
            if m == models[0]:
                dataset_counts[ds] = dataset_counts.get(ds, 0) + 1

acc_matrix = {}
for m in models:
    for ds in data[m]:
        if ds not in acc_matrix:
            acc_matrix[ds] = {}
        scores = data[m][ds]
        acc_matrix[ds][m] = (sum(scores) / len(scores)) * 100.0 if scores else 0.0

print("=== ACCURACY MATRIX PER DATASET ACROSS ALIGNED 8 MODELS (%) ===")
header = 'Dataset'.ljust(27) + ' | ' + ' | '.join([m[:9].ljust(9) for m in models])
print(header)
print('-' * len(header))

ds_stats = []

for ds in sorted(acc_matrix.keys()):
    accs = [acc_matrix[ds][m] for m in models]
    row_str = ds.ljust(27) + ' | ' + ' | '.join([f'{v:9.2f}' for v in accs])
    print(row_str)
    
    mean_acc = sum(accs) / len(accs)
    min_acc = min(accs)
    max_acc = max(accs)
    variance = sum((x - mean_acc)**2 for x in accs) / len(accs)
    std_dev = math.sqrt(variance)
    count = dataset_counts[ds]
    ds_stats.append({
        'ds': ds,
        'mean': mean_acc,
        'min': min_acc,
        'max': max_acc,
        'std': std_dev,
        'count': count,
        'accs': dict(zip(models, accs))
    })

print("\n" + "="*90)
print("=== BENCHMARK DATASETS RANKED BY MEAN ACCURACY ===")
print("="*90)

ds_stats.sort(key=lambda x: x['mean'], reverse=True)

for s in ds_stats:
    print(f"{s['ds']:<27} | Count: {s['count']:<4} | Mean Acc: {s['mean']:6.2f}% | Range: [{s['min']:5.2f}% - {s['max']:5.2f}%] | StdDev: {s['std']:5.2f}")
