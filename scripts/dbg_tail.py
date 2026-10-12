"""Debug: redness and colour fractions around the last ring for a few photos (helps design the sleeve rules)."""
import sys, csv
import numpy as np
sys.path.insert(0, ".")
from gauge.detect import load, detect, ring_mask, grey_mask
from gauge.measure import straighten
from scipy.signal import find_peaks
R = list(csv.DictReader(open("data/photo_reads.csv")))
for k in map(int, sys.argv[1:]):
    im = load("way points/" + R[k]["photo"]); det = detect(im); L = det["t1"] - det["t0"]
    core, ys = straighten(im, det, 0.6 * L + 80, 0.5 * L + 150)
    redf = ring_mask(core).mean(1); greyf = grey_mask(core).mean(1)
    r, g, b = core[..., 0], core[..., 1], core[..., 2]
    red = np.clip(np.median(r - np.maximum(g, b), 1), 0, None)
    p = float(R[k]["pitch_px"]); last = float(R[k]["last_y"])
    i = int(np.argmin(abs(ys - last)))
    print(f"#{k} rings {R[k]['rings']} pitch {p} last_y {last}")
    for j in range(i - int(0.6 * p), min(len(ys), i + int(1.8 * p)), 3):
        v = core[j, core.shape[1] // 2].tolist()
        print(f"  y {ys[j]:7.0f} {'*' if j == i else ' '} redf {redf[j]:.2f} red {red[j]:5.1f} grey {greyf[j]:.2f} rgb {v}")
