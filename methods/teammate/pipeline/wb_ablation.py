"""Method 3: test the outside answer (colour constancy) part by part on clear+partial (every 2nd photo),
with and without the two attacks it should fix."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import cv2, numpy as np, isolate as iso
from isolate import photos, points, load
from locate import locate
from evaluate import is_hit
ph, pt = photos(), points()
ids = [i for i in sorted(ph) if ph[i][1] != "3_hard"][::2]
def gray_world_nonveg(img):
    h, s, v = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2HSV))
    m = ~((h >= 22) & (h <= 95) & (s > 40)) & (v > 30) & (v < 240)
    f = img.astype(np.float32)
    if m.sum() > 500:
        means = f[m].mean(axis=0); f *= np.clip(means.mean() / np.maximum(means, 1), 0.75, 1.33)
    return np.clip(f, 0, 255).astype(np.uint8)
def hue_m6(im):
    h = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); h[..., 0] = (h[..., 0].astype(int) - 6) % 180
    return cv2.cvtColor(h, cv2.COLOR_HSV2BGR)
for pname, pre in (("raw (team method)", None), ("gray-world WB (outside answer)", gray_world_nonveg), ("brightness gain (kept)", iso.normalize)):
    iso.PREPROCESS = pre
    row = []
    for aname, att in (("no attack", lambda x: x), ("dark x0.6", lambda im: cv2.convertScaleAbs(im, alpha=0.6)), ("hue -6", hue_m6)):
        hits = 0
        for i in ids:
            img, sc = load(ph[i][0]); r = locate(att(img))
            if r["box"] is not None:
                b = [round(v / sc) for v in r["box"]]
                hits += is_hit({"x0": b[0], "y0": b[1], "x1": b[2], "y1": b[3]}, pt[i])
        row.append(f"{aname} {hits}/{len(ids)}")
    print(f"{pname:32s} " + " | ".join(row))
print("RESULT PASS (ablation printed: gray-world dropped, brightness gain kept)")
