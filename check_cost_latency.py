import glob
import csv
import os

csv.field_size_limit(100000000)

target_dirs = [
    r"D:\AetherFlow\cleaned\aligned_8_models",
    r"D:\AetherFlow\cleaned\individual"
]

for t_dir in target_dirs:
    print(f"=== CHECKING COSTE AND LATENCY IN: {os.path.basename(t_dir)} ===")
    csv_files = sorted(glob.glob(os.path.join(t_dir, '*.csv')))
    
    for f in csv_files:
        name = os.path.basename(f)
        with open(f, mode='r', encoding='utf-8', errors='ignore') as fp:
            reader = csv.DictReader(fp)
            fieldnames = reader.fieldnames
            
            cost_cols = [c for c in fieldnames if 'cost' in c.lower()]
            lat_cols = [c for c in fieldnames if 'latency' in c.lower() or 'time' in c.lower()]
            
            costs = []
            lats = []
            
            for r in reader:
                if cost_cols:
                    try:
                        costs.append(float(r[cost_cols[0]]))
                    except:
                        pass
                if lat_cols:
                    try:
                        lats.append(float(r[lat_cols[0]]))
                    except:
                        pass
            
            c_str = f"Mean Cost: ${sum(costs)/len(costs):.6f}" if costs else "No Cost Data"
            l_str = f"Mean Latency: {sum(lats)/len(lats):.4f}s" if lats else "No Latency Data"
            print(f"  {name:<25} | Cols: {fieldnames} | {c_str} | {l_str}")
    print()
