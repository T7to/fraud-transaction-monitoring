import shutil
from pathlib import Path

import kagglehub

# original upload by the PaySim author
path = Path(kagglehub.dataset_download("ealaxi/paysim1"))
csv_file = next(path.glob("*.csv"))

shutil.copy(csv_file, "data/paysim.csv")
print("Copied", csv_file.name, "to data/paysim.csv")
