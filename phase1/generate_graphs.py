import csv
import glob
import os
import shutil

import matplotlib
matplotlib.use('Agg') # Headless mode for saving figures
import matplotlib.pyplot as plt

source_dir = r"c:\Users\Abdul Raheem\Desktop\New folder\cleaned\individual"
output_dir = r"c:\Users\Abdul Raheem\Desktop\New folder\graphs"
artifact_dir = r"C:\Users\Abdul Raheem\.gemini\antigravity-ide\brain\abd950b0-3a48-46c2-a13b-f50ee51d2570"

os.makedirs(output_dir, exist_ok=True)
csv_files = glob.glob(os.path.join(source_dir, "*.csv"))

print(f"Generating accuracy graphs for {len(csv_files)} models...")

model_results = {}

for f_path in sorted(csv_files):
    name = os.path.basename(f_path)
    model_name = name.replace('.csv', '')
    
    # Store sum and count per dataset_name
    class_scores = {}
    class_counts = {}
    
    with open(f_path, mode='r', encoding='utf-8', errors='ignore') as fp:
        reader = csv.DictReader(fp)
        for r in reader:
            ds = r.get('dataset_name', '').strip()
            score_str = r.get('score', '0')
            if not ds:
                continue
            try:
                score = float(score_str)
            except ValueError:
                score = 0.0
                
            class_scores[ds] = class_scores.get(ds, 0.0) + score
            class_counts[ds] = class_counts.get(ds, 0) + 1
            
    # Calculate percentage accuracy per class
    classes = []
    accuracies = []
    counts = []
    
    for ds in sorted(class_scores.keys()):
        acc = (class_scores[ds] / class_counts[ds]) * 100.0 if class_counts[ds] > 0 else 0.0
        classes.append(ds)
        accuracies.append(acc)
        counts.append(class_counts[ds])
        
    model_results[model_name] = dict(zip(classes, accuracies))
    
    # Sort classes by accuracy descending
    sorted_pairs = sorted(zip(classes, accuracies, counts), key=lambda x: x[1], reverse=True)
    sorted_classes = [p[0] for p in sorted_pairs]
    sorted_accs = [p[1] for p in sorted_pairs]
    
    # Generate Matplotlib Bar Graph
    fig, ax = plt.subplots(figsize=(14, 7), dpi=150)
    
    # Modern color palette gradient
    colors = plt.cm.viridis([0.25 + 0.65 * (acc / 100.0) for acc in sorted_accs])
    bars = ax.bar(sorted_classes, sorted_accs, color=colors, edgecolor='#222222', linewidth=0.8, width=0.6)
    
    # Annotate bars with accuracy percentage
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 4),  # 4 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom',
                    fontsize=9, fontweight='bold', color='#111111')
        
    ax.set_title(f'Accuracy / Success Rate by Benchmark Class — {model_name}', fontsize=15, fontweight='bold', pad=15)
    ax.set_xlabel('Benchmark Class (dataset_name)', fontsize=12, fontweight='bold', labelpad=10)
    ax.set_ylabel('Accuracy Score (%)', fontsize=12, fontweight='bold', labelpad=10)
    ax.set_ylim(0, max(100.0, max(sorted_accs, default=0) + 12))
    ax.set_xticklabels(sorted_classes, rotation=40, ha='right', fontsize=10)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    
    out_png_name = f"{model_name}_accuracy.png"
    out_png_path = os.path.join(output_dir, out_png_name)
    plt.savefig(out_png_path, bbox_inches='tight')
    plt.close(fig)
    
    # Copy to artifact folder for markdown embedding
    artifact_png_path = os.path.join(artifact_dir, out_png_name)
    shutil.copy(out_png_path, artifact_png_path)
    
    print(f"  ✓ Saved graph for {model_name}: {out_png_name}")

print("\nAll accuracy graphs generated successfully!")
