"""Dev cache: full images as .npy so the reader loop does not re-decode JPEGs (data/ is gitignored)."""
import csv, os, sys
import numpy as np
sys.path.insert(0, ".")
from gauge.detect import load
os.makedirs("data/cache", exist_ok=True)
for k, r in enumerate(csv.DictReader(open("data/index.csv"))):
    f = f"data/cache/{k:03d}.npy"
    if not os.path.exists(f):
        np.save(f, load("way points/" + r["photo"]).astype(np.uint8))
