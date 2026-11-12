import shutil
from pathlib import Path

import kagglehub

path = Path(kagglehub.dataset_download("ealaxi/paysim1"))
csv_files = list(path.glob("*.csv"))
print("Downloaded", csv_files)

target = Path("data/paysim.csv")
shutil.copy(csv_files[0], target)
print("Copied to", target)