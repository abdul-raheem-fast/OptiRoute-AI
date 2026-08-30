import shutil
import os

source_dir = r"D:\AetherFlow"
cleaned_dir = os.path.join(source_dir, "cleaned")
zip_output = os.path.join(source_dir, "cleaned_datasets")

print(f"Zipping {cleaned_dir} to {zip_output}.zip...")
shutil.make_archive(zip_output, 'zip', cleaned_dir)
print("Zipping completed successfully.")
