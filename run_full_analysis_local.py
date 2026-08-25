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
print(f"Found {len(csv_files)} dataset files in aligned_8_models.\n")

sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.size': 11})

summary_data = []

# --- 1. Generate Individual Accuracy Bar Charts per Model ---
print("=== GENERATING ACCURACY GRAPHS PER MODEL ===")
for f in csv_files:
    m_name = os.path.basename(f).replace('.csv', '')
    df = pd.read_csv(f)
    
    df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0.0)
    df['cost'] = pd.to_numeric(df['cost'], errors='coerce').fillna(0.0)
    df['estimated_latency'] = pd.to_numeric(df['estimated_latency'], errors='coerce').fillna(0.0)
    
    # Store summary stats for model
    mean_acc = df['score'].mean() * 100.0
    mean_cost = df['cost'].mean()
    mean_lat = df['estimated_latency'].mean()
    
    summary_data.append({
        'Model': m_name,
        'Accuracy (%)': mean_acc,
        'Avg Cost ($)': mean_cost,
        'Cost per 1k ($)': mean_cost * 1000.0,
        'Avg Latency (s)': mean_lat
    })
    
    # Group accuracy per dataset_name
    acc_df = df.groupby('dataset_name')['score'].mean().reset_index()
    acc_df['Accuracy (%)'] = acc_df['score'] * 100.0
    acc_df = acc_df.sort_values(by='Accuracy (%)', ascending=False)
    
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = sns.barplot(x='dataset_name', y='Accuracy (%)', data=acc_df, palette='viridis', hue='dataset_name', legend=False, ax=ax)
    ax.set_title(f'Model Accuracy by Benchmark Class: {m_name}', fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Benchmark Class', fontsize=12, fontweight='bold')
    ax.set_ylabel('Accuracy (%)', fontsize=12, fontweight='bold')
    ax.set_ylim(0, 100)
    plt.xticks(rotation=15)
    
    for p in ax.patches:
        h = p.get_height()
        ax.annotate(f'{h:.1f}%', (p.get_x() + p.get_width() / 2., h),
                    ha='center', va='bottom', fontsize=10, fontweight='bold', xytext=(0, 3), textcoords='offset points')
        
    plt.tight_layout()
    png_path = os.path.join(out_dir, f"{m_name}_accuracy.png")
    plt.savefig(png_path, dpi=300)
    plt.close()
    print(f"  [x] Saved {m_name} accuracy graph -> {png_path}")

metrics_df = pd.DataFrame(summary_data)

# --- 2. Cost Comparison Graph ---
print("\n=== GENERATING COST COMPARISON GRAPH ===")
fig, ax = plt.subplots(figsize=(10, 5))
cost_sorted = metrics_df.sort_values(by='Avg Cost ($)', ascending=True)
bars = sns.barplot(x='Avg Cost ($)', y='Model', data=cost_sorted, palette='Blues_r', hue='Model', legend=False, ax=ax)
ax.set_title('Average Cost per Query (USD) by Model', fontsize=14, fontweight='bold', pad=15)
ax.set_xlabel('Average Cost ($)', fontsize=12, fontweight='bold')
ax.set_ylabel('Model', fontsize=12, fontweight='bold')
for p in ax.patches:
    w = p.get_width()
    ax.annotate(f'${w:.5f}', (w, p.get_y() + p.get_height()/2),
                ha='left', va='center', fontsize=10, fontweight='bold', xytext=(5, 0), textcoords='offset points')
plt.tight_layout()
cost_png = os.path.join(out_dir, "model_cost_comparison.png")
plt.savefig(cost_png, dpi=300)
plt.close()
print(f"  [x] Saved cost comparison graph -> {cost_png}")

# --- 3. Latency Comparison Graph ---
print("\n=== GENERATING LATENCY COMPARISON GRAPH ===")
fig, ax = plt.subplots(figsize=(10, 5))
lat_sorted = metrics_df.sort_values(by='Avg Latency (s)', ascending=True)
bars = sns.barplot(x='Avg Latency (s)', y='Model', data=lat_sorted, palette='Oranges_r', hue='Model', legend=False, ax=ax)
ax.set_title('Average Latency / Response Time (Seconds) by Model', fontsize=14, fontweight='bold', pad=15)
ax.set_xlabel('Average Latency (Seconds)', fontsize=12, fontweight='bold')
ax.set_ylabel('Model', fontsize=12, fontweight='bold')
for p in ax.patches:
    w = p.get_width()
    ax.annotate(f'{w:.3f}s', (w, p.get_y() + p.get_height()/2),
                ha='left', va='center', fontsize=10, fontweight='bold', xytext=(5, 0), textcoords='offset points')
plt.tight_layout()
lat_png = os.path.join(out_dir, "model_latency_comparison.png")
plt.savefig(lat_png, dpi=300)
plt.close()
print(f"  [x] Saved latency comparison graph -> {lat_png}")

# --- 4. Tradeoff Scatter Plots ---
print("\n=== GENERATING TRADEOFF SCATTER PLOTS ===")
fig, ax = plt.subplots(figsize=(9, 6))
ax.scatter(metrics_df['Cost per 1k ($)'], metrics_df['Accuracy (%)'], color='#7570b3', s=150, edgecolors='black', zorder=5)
for _, row in metrics_df.iterrows():
    ax.annotate(row['Model'], (row['Cost per 1k ($)'], row['Accuracy (%)']),
                xytext=(8, -4), textcoords='offset points', fontsize=11, fontweight='bold')
ax.set_xscale('log')
ax.set_xlabel('Cost per 1,000 Queries (USD Log-scale)', fontsize=12, fontweight='bold')
ax.set_ylabel('Mean Accuracy (%)', fontsize=12, fontweight='bold')
ax.set_title('Tradeoff Analysis: Mean Accuracy vs. Cost (USD per 1k Queries)', fontsize=13, fontweight='bold', pad=15)
ax.grid(True, which='both', ls='--', alpha=0.5)
plt.tight_layout()
trade_cost_png = os.path.join(out_dir, "accuracy_vs_cost_tradeoff.png")
plt.savefig(trade_cost_png, dpi=300)
plt.close()
print(f"  [x] Saved accuracy vs cost tradeoff plot -> {trade_cost_png}")

fig, ax = plt.subplots(figsize=(9, 6))
ax.scatter(metrics_df['Avg Latency (s)'], metrics_df['Accuracy (%)'], color='#1b9e77', s=150, edgecolors='black', zorder=5)
for _, row in metrics_df.iterrows():
    ax.annotate(row['Model'], (row['Avg Latency (s)'], row['Accuracy (%)']),
                xytext=(8, -4), textcoords='offset points', fontsize=11, fontweight='bold')
ax.set_xlabel('Average Latency (Seconds)', fontsize=12, fontweight='bold')
ax.set_ylabel('Mean Accuracy (%)', fontsize=12, fontweight='bold')
ax.set_title('Tradeoff Analysis: Mean Accuracy vs. Response Latency', fontsize=13, fontweight='bold', pad=15)
ax.grid(True, ls='--', alpha=0.5)
plt.tight_layout()
trade_lat_png = os.path.join(out_dir, "accuracy_vs_latency_tradeoff.png")
plt.savefig(trade_lat_png, dpi=300)
plt.close()
print(f"  [x] Saved accuracy vs latency tradeoff plot -> {trade_lat_png}")

print("\n" + "="*85)
print("=== COMPREHENSIVE PERFORMANCE MATRIX ===")
print("="*85)
summary_sorted = metrics_df.sort_values(by='Accuracy (%)', ascending=False)
print(summary_sorted.to_string(index=False))
