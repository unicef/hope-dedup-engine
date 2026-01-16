import shutil
from pathlib import Path

source_images = Path("src/hope_dedup_engine/ui/theme/static/images/")
destination = "docs/src/images/"

for ext in [".png"]:
    for filename in source_images.glob(f"hope_*{ext}"):
        shutil.copy(str(filename), destination)
