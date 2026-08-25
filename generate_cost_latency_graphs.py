import glob
import csv
import os
import math
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

csv.field_size_limit(100000000)

source_dir = r"D:\Datasets (FYP)\cleaned\aligned_8_models"
out_dir = r"D:\Datasets (FYP)\graphs_output"
os.makedirs(out_dir, exist_ok=True)

csv_files = sorted(glob.glob(os.path.join(source_dir, "*.csv")))
models = [os.path.basename(f).replace('.csv', '') for f in csv_files]

# Store stats: model -> {'acc': mean_acc, 'cost': mean_cost, 'latency': mean_latency}
stats = {m: {} for m in models}
class_stats = {} # class -> model -> {'acc': x, 'cost': y, 'latency': z}

for f, m in zip(csv_files, models):
    scores = []
    costs = []
    lats = []
    
    with open(f, mode='r', encoding='utf-8', errors='ignore') as fp:
        reader = csv.DictReader(fp)
        for r in reader:
            ds = r['dataset_name'].strip()
            score = float(r.get('score', 0.0)) * 100.0
            cost = float(r.get('cost', 0.0))
            lat = float(r.get('estimated_latency', 0.0))
            
            scores.append(score)
            costs.append(cost)
            lats.append(lat)
            
            if ds not in class_stats:
                class_stats[ds] = {}
            if m not in class_stats[ds]:
                class_stats[ds][m] = {'scores': [], 'costs': [], 'lats': []}
                
            class_stats[ds][m]['scores'].append(score)
            class_stats[ds][m]['costs'].append(cost)
            class_stats[ds][m]['lats'].append(lat)
            
    stats[m]['mean_acc'] = sum(scores) / len(scores) if scores else 0.0
    stats[m]['mean_cost'] = sum(costs) / len(costs) if costs else 0.0
    stats[m]['total_cost'] = sum(costs)
    stats[m]['mean_latency'] = sum(lats) / len(lats) if lats else 0.0

sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.size': 11})

# -------------------------------------------------------------
# 1. Average Cost per Query Comparison Bar Chart
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6))
model_list = sorted(models, key=lambda x: stats[x]['mean_cost'])
costs_usd = [stats[m]['mean_cost'] for m in model_list]

bars = ax.barh(model_list, costs_usd, color='#2b5c8f', edgecolor='black', alpha=0.85)

for bar in bars:
    width = bar.get_width()
    ax.text(width + (max(costs_usd)*0.01), bar.get_y() + bar.get_height()/2,
            f"${width:.6f}", ha='left', va='center', fontsize=10, fontweight='bold')

ax.set_xlabel('Average Cost per Query (USD)', fontsize=12, fontweight='bold')
ax.set_title('LLM Evaluation: Average Cost per Query across Models', fontsize=14, fontweight='bold', pad=15)
ax.set_xlim(0, max(costs_usd) * 1.15)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, "average_cost_comparison.png"), dpi=300)
plt.close()
print("✓ Saved average_cost_comparison.png")

# -------------------------------------------------------------
# 2. Average Latency Comparison Bar Chart
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6))
model_list_lat = sorted(models, key=lambda x: stats[x]['mean_latency'])
lats_sec = [stats[m]['mean_latency'] for m in model_list_lat]

bars = ax.barh(model_list_lat, lats_sec, color='#d95f02', edgecolor='black', alpha=0.85)

for bar in bars:
    width = bar.get_width()
    ax.text(width + (max(lats_sec)*0.01), bar.get_y() + bar.get_height()/2,
            f"{width:.3f}s", ha='left', va='center', fontsize=10, fontweight='bold')

ax.set_xlabel('Average Latency / Response Time (Seconds)', fontsize=12, fontweight='bold')
ax.set_title('LLM Evaluation: Average Latency per Query across Models', fontsize=14, fontweight='bold', pad=15)
ax.set_xlim(0, max(lats_sec) * 1.15)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, "average_latency_comparison.png"), dpi=300)
plt.close()
print("✓ Saved average_latency_comparison.png")

# -------------------------------------------------------------
# 3. Accuracy vs. Cost Scatter Tradeoff Plot
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 7))

x_costs = [stats[m]['mean_cost'] * 1000 for m in models] # cost per 1000 queries
y_accs = [stats[m]['mean_acc'] for m in models]

ax.scatter(x_costs, y_accs, color='#7570b3', s=160, zorder=5, edgecolor='black', alpha=0.9)

for m, x, y in zip(models, x_costs, y_accs):
    ax.annotate(m, (x, y), xytext=(8, -4), textcoords='offset points', fontsize=11, fontweight='bold')

ax.set_xlabel('Cost per 1,000 Queries (USD)', fontsize=12, fontweight='bold')
ax.set_ylabel('Mean Accuracy (%)', fontsize=12, fontweight='bold')
ax.set_title('Efficiency Tradeoff: Mean Accuracy vs. Cost (USD per 1k Queries)', fontsize=14, fontweight='bold', pad=15)
ax.set_xscale('log') # Log scale for costs due to wide range
plt.tight_layout()
plt.savefig(os.path.join(out_dir, "accuracy_vs_cost_tradeoff.png"), dpi=300)
plt.close()
print("✓ Saved accuracy_vs_cost_tradeoff.png")

# -------------------------------------------------------------
# 4. Accuracy vs. Latency Scatter Tradeoff Plot
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 7))

x_lats = [stats[m]['mean_latency'] for m in models]
y_accs = [stats[m]['mean_acc'] for m in models]

ax.scatter(x_lats, y_accs, color='#1b9e77', s=160, zorder=5, edgecolor='black', alpha=0.9)

for m, x, y in zip(models, x_lats, y_accs):
    ax.annotate(m, (x, y), xytext=(8, -4), textcoords='offset points', fontsize=11, fontweight='bold')

ax.set_xlabel('Average Latency (Seconds)', fontsize=12, fontweight='bold')
ax.set_ylabel('Mean Accuracy (%)', fontsize=12, fontweight='bold')
ax.set_title('Performance Tradeoff: Mean Accuracy vs. Response Latency', fontsize=14, fontweight='bold', pad=15)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, "accuracy_vs_latency_tradeoff.png"), dpi=300)
plt.close()
print("✓ Saved accuracy_vs_latency_tradeoff.png")

print("\nAll Cost & Latency graphs generated successfully!")
