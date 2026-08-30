import json
import os

notebook_content = {
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# LLM Model Accuracy Analysis by Benchmark Class\n",
    "This notebook analyzes model accuracy across individual benchmark classes (`dataset_name`) from cleaned evaluation datasets.\n",
    "\n",
    "### Instructions for Google Colab:\n",
    "1. Run **Cell 1** to upload your `cleaned_datasets.zip` or individual CSV files directly.\n",
    "2. Run **Cell 2 & 3** to automatically parse the files, calculate accuracy rates per class, and display separate visualization graphs for every model!"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Cell 1: Environment Setup & File Upload / Unzipping\n",
    "import os\n",
    "import glob\n",
    "import zipfile\n",
    "import pandas as pd\n",
    "import numpy as np\n",
    "import matplotlib.pyplot as plt\n",
    "import seaborn as sns\n",
    "\n",
    "# Set aesthetic style\n",
    "sns.set_theme(style=\"whitegrid\")\n",
    "plt.rcParams['font.family'] = 'sans-serif'\n",
    "\n",
    "# Check for local directory or prompt upload in Colab\n",
    "input_dir = 'cleaned/individual'\n",
    "if not os.path.exists(input_dir):\n",
    "    if os.path.exists('cleaned_datasets.zip'):\n",
    "        print('Unzipping cleaned_datasets.zip...')\n",
    "        with zipfile.ZipFile('cleaned_datasets.zip', 'r') as zip_ref:\n",
    "            zip_ref.extractall('./')\n",
    "    else:\n",
    "        try:\n",
    "            from google.colab import files\n",
    "            print('Please upload cleaned_datasets.zip or your individual model CSV files:')\n",
    "            uploaded = files.upload()\n",
    "            for fname in uploaded.keys():\n",
    "                if fname.endswith('.zip'):\n",
    "                    with zipfile.ZipFile(fname, 'r') as zip_ref:\n",
    "                        zip_ref.extractall('./')\n",
    "        except ImportError:\n",
    "            input_dir = '.'\n",
    "\n",
    "# Find target directory containing CSV files\n",
    "if os.path.exists('cleaned/individual'):\n",
    "    data_path = 'cleaned/individual'\n",
    "elif os.path.exists('individual'):\n",
    "    data_path = 'individual'\n",
    "else:\n",
    "    data_path = '.'\n",
    "\n",
    "csv_files = glob.glob(os.path.join(data_path, '*.csv'))\n",
    "print(f'Found {len(csv_files)} dataset CSV files in \"{data_path}\":')\n",
    "for f in sorted(csv_files):\n",
    "    print('  -', os.path.basename(f))\n"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Generate Separate Accuracy Graphs per Model"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Cell 2: Calculate Accuracy per Class & Plot Graphs\n",
    "os.makedirs('graphs_output', exist_ok=True)\n",
    "palette = sns.color_palette('viridis')\n",
    "\n",
    "for f_path in sorted(csv_files):\n",
    "    filename = os.path.basename(f_path)\n",
    "    model_title = filename.replace('.csv', '')\n",
    "    \n",
    "    df = pd.read_csv(f_path, low_memory=False)\n",
    "    if 'score' not in df.columns or 'dataset_name' not in df.columns:\n",
    "        print(f'Skipping {filename}: Missing required columns.')\n",
    "        continue\n",
    "        \n",
    "    # Ensure score is numeric\n",
    "    df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0.0)\n",
    "    \n",
    "    # Calculate accuracy (% mean score) per benchmark class\n",
    "    stats = df.groupby('dataset_name').agg(\n",
    "        accuracy=('score', lambda x: x.mean() * 100),\n",
    "        count=('score', 'count')\n",
    "    ).reset_index()\n",
    "    \n",
    "    # Sort by accuracy descending\n",
    "    stats = stats.sort_values(by='accuracy', ascending=False)\n",
    "    \n",
    "    # Create Figure\n",
    "    plt.figure(figsize=(14, 7))\n",
    "    ax = sns.barplot(\n",
    "        data=stats, \n",
    "        x='dataset_name', \n",
    "        y='accuracy', \n",
    "        palette='crest',\n",
    "        edgecolor='black',\n",
    "        linewidth=1\n",
    "    )\n",
    "    \n",
    "    # Annotate bars with accuracy percentage\n",
    "    for p in ax.patches:\n",
    "        height = p.get_height()\n",
    "        if not np.isnan(height):\n",
    "            ax.annotate(\n",
    "                f'{height:.1f}%',\n",
    "                (p.get_x() + p.get_width() / 2., height),\n",
    "                ha='center', va='bottom',\n",
    "                fontsize=10, fontweight='bold',\n",
    "                color='#111111',\n",
    "                xytext=(0, 4), textcoords='offset points'\n",
    "            )\n",
    "            \n",
    "    plt.title(f'Success Rate / Accuracy by Benchmark Class: {model_title}', fontsize=16, fontweight='bold', pad=15)\n",
    "    plt.xlabel('Benchmark Class (dataset_name)', fontsize=12, labelpad=10, fontweight='bold')\n",
    "    plt.ylabel('Accuracy Score (%)', fontsize=12, labelpad=10, fontweight='bold')\n",
    "    plt.xticks(rotation=45, ha='right', fontsize=11)\n",
    "    plt.ylim(0, max(100, stats['accuracy'].max() + 10))\n",
    "    plt.grid(axis='y', linestyle='--', alpha=0.7)\n",
    "    plt.tight_layout()\n",
    "    \n",
    "    # Save and show\n",
    "    save_path = os.path.join('graphs_output', f'{model_title}_accuracy.png')\n",
    "    plt.savefig(save_path, dpi=300, bbox_inches='tight')\n",
    "    plt.show()\n",
    "    plt.close()\n",
    "    \n",
    "    print(f'✓ Graph saved for {model_title} -> {save_path}')\n"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Combined Model Accuracy Summary Table"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Cell 3: Overall Benchmark Class Accuracy Comparison Table\n",
    "all_stats = []\n",
    "for f_path in sorted(csv_files):\n",
    "    filename = os.path.basename(f_path)\n",
    "    model_name = filename.replace('.csv', '')\n",
    "    df = pd.read_csv(f_path, low_memory=False)\n",
    "    df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0.0)\n",
    "    grouped = df.groupby('dataset_name')['score'].mean() * 100\n",
    "    grouped.name = model_name\n",
    "    all_stats.append(grouped)\n",
    "\n",
    "comparison_df = pd.concat(all_stats, axis=1).round(2)\n",
    "comparison_df.index.name = 'Benchmark Class'\n",
    "print('=== Accuracy (%) Summary across Models by Benchmark Class ===')\n",
    "display(comparison_df)\n"
   ]
  }
 ],
 "metadata": {
  "language_info": {
   "name": "python"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}

notebook_path = r"D:\AetherFlow\phase1\model_accuracy_analysis.ipynb"
with open(notebook_path, mode='w', encoding='utf-8') as f:
    json.dump(notebook_content, f, indent=2)

print(f"Notebook created successfully at: {notebook_path}")
