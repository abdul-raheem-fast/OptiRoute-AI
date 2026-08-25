import glob
import csv
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

csv.field_size_limit(100000000)

source_dir = r"D:\Datasets (FYP)\cleaned\aligned_8_models"
out_dir = r"D:\Datasets (FYP)\graphs_output"
os.makedirs(out_dir, exist_ok=True)

csv_files = sorted(glob.glob(os.path.join(source_dir, "*.csv")))

dfs = []
for f in csv_files:
    m_name = os.path.basename(f).replace('.csv', '')
    df = pd.read_csv(f)
    df['model'] = m_name
    df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0.0)
    df['cost'] = pd.to_numeric(df['cost'], errors='coerce').fillna(0.0)
    df['estimated_latency'] = pd.to_numeric(df['estimated_latency'], errors='coerce').fillna(0.0)
    dfs.append(df)

combined_df = pd.concat(dfs, ignore_index=True)

sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.size': 11})

# -------------------------------------------------------------
# 1. Average Cost per Benchmark Class (Overall Across Models)
# -------------------------------------------------------------
class_cost = combined_df.groupby('dataset_name')['cost'].mean().reset_index()
class_cost['cost_usd'] = class_cost['cost']
class_cost = class_cost.sort_values(by='cost_usd', ascending=False)

fig, ax = plt.subplots(figsize=(10, 5))
bars = sns.barplot(x='dataset_name', y='cost_usd', data=class_cost, palette='Blues_r', hue='dataset_name', legend=False, ax=ax)
ax.set_title('Average Cost per Query (USD) by Benchmark Class', fontsize=14, fontweight='bold', pad=15)
ax.set_xlabel('Benchmark Class', fontsize=12, fontweight='bold')
ax.set_ylabel('Average Cost ($)', fontsize=12, fontweight='bold')
plt.xticks(rotation=15)

for p in ax.patches:
    h = p.get_height()
    ax.annotate(f'${h:.5f}', (p.get_x() + p.get_width() / 2., h),
                ha='center', va='bottom', fontsize=10, fontweight='bold', xytext=(0, 3), textcoords='offset points')

plt.tight_layout()
cost_class_png = os.path.join(out_dir, "avg_cost_per_class.png")
plt.savefig(cost_class_png, dpi=300)
plt.close()
print(f"  [x] Saved average cost per class graph -> {cost_class_png}")

# -------------------------------------------------------------
# 2. Average Latency per Benchmark Class (Overall Across Models)
# -------------------------------------------------------------
class_lat = combined_df.groupby('dataset_name')['estimated_latency'].mean().reset_index()
class_lat['latency_s'] = class_lat['estimated_latency']
class_lat = class_lat.sort_values(by='latency_s', ascending=False)

fig, ax = plt.subplots(figsize=(10, 5))
bars = sns.barplot(x='dataset_name', y='latency_s', data=class_lat, palette='Oranges_r', hue='dataset_name', legend=False, ax=ax)
ax.set_title('Average Latency / Response Time (Seconds) by Benchmark Class', fontsize=14, fontweight='bold', pad=15)
ax.set_xlabel('Benchmark Class', fontsize=12, fontweight='bold')
ax.set_ylabel('Average Latency (Seconds)', fontsize=12, fontweight='bold')
plt.xticks(rotation=15)

for p in ax.patches:
    h = p.get_height()
    ax.annotate(f'{h:.3f}s', (p.get_x() + p.get_width() / 2., h),
                ha='center', va='bottom', fontsize=10, fontweight='bold', xytext=(0, 3), textcoords='offset points')

plt.tight_layout()
lat_class_png = os.path.join(out_dir, "avg_latency_per_class.png")
plt.savefig(lat_class_png, dpi=300)
plt.close()
print(f"  [x] Saved average latency per class graph -> {lat_class_png}")

# -------------------------------------------------------------
# 3. Cost by Class & Model Breakdown
# -------------------------------------------------------------
model_class_cost = combined_df.groupby(['dataset_name', 'model'])['cost'].mean().reset_index()

fig, ax = plt.subplots(figsize=(12, 6))
sns.barplot(x='dataset_name', y='cost', hue='model', data=model_class_cost, palette='tab10', ax=ax)
ax.set_title('Average Cost per Query ($) by Benchmark Class & Model', fontsize=14, fontweight='bold', pad=15)
ax.set_xlabel('Benchmark Class', fontsize=12, fontweight='bold')
ax.set_ylabel('Average Cost ($)', fontsize=12, fontweight='bold')
plt.xticks(rotation=15)
plt.legend(title='Model', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.tight_layout()
cost_model_class_png = os.path.join(out_dir, "cost_by_class_and_model.png")
plt.savefig(cost_model_class_png, dpi=300)
plt.close()
print(f"  [x] Saved cost breakdown graph -> {cost_model_class_png}")

# -------------------------------------------------------------
# 4. Latency by Class & Model Breakdown
# -------------------------------------------------------------
model_class_lat = combined_df.groupby(['dataset_name', 'model'])['estimated_latency'].mean().reset_index()

fig, ax = plt.subplots(figsize=(12, 6))
sns.barplot(x='dataset_name', y='estimated_latency', hue='model', data=model_class_lat, palette='tab10', ax=ax)
ax.set_title('Average Response Latency (Seconds) by Benchmark Class & Model', fontsize=14, fontweight='bold', pad=15)
ax.set_xlabel('Benchmark Class', fontsize=12, fontweight='bold')
ax.set_ylabel('Average Latency (Seconds)', fontsize=12, fontweight='bold')
plt.xticks(rotation=15)
plt.legend(title='Model', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.tight_layout()
lat_model_class_png = os.path.join(out_dir, "latency_by_class_and_model.png")
plt.savefig(lat_model_class_png, dpi=300)
plt.close()
print(f"  [x] Saved latency breakdown graph -> {lat_model_class_png}")

print("\n" + "="*85)
print("=== AVERAGE COST PER BENCHMARK CLASS ===")
print("="*85)
print(class_cost.to_string(index=False))

print("\n" + "="*85)
print("=== AVERAGE LATENCY PER BENCHMARK CLASS ===")
print("="*85)
print(class_lat.to_string(index=False))
