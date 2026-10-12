"""Try to break method 3+ (loophole hunt). Each attack prints what it found; nothing is tuned here.

python pipeline/breakit.py
"""
import csv, pathlib, sys, time
import cv2, numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from isolate import ROOT, photos, points, load
from locate import locate, visits, CONF_TH
from evaluate import is_hit, read_locate

ph, pt, vis = photos(), points(), visits()
if "--wb" in sys.argv:
    import isolate as _iso
    _iso.PREPROCESS = _iso.normalize
    print("(colour constancy ON)")
if "--a5" in sys.argv:
    ONLY_A5 = True
else:
    ONLY_A5 = False
col, m3 = read_locate("colour"), read_locate("method3")
groups = {}
for i, k in vis.items():
    groups.setdefault(k, []).append(i)

if ONLY_A5:
    pass
print("A1  cross-day alignment (the original method-3 idea)")
a = list(csv.DictReader(open(ROOT / "results/align_full.csv")))
print(f"    photos aligned to another day with >= 25 RANSAC inliers: {sum(1 for r in a if r['x'])}/128 -> idea broken in this crop")

print("A2  visits where neither shot is confident (sibling transfer has nothing to give)")
unsure = [k for k, g in groups.items() if all(float(col[i]["score"] or 0) < CONF_TH for i in g)]
single = [k for k, g in groups.items() if len(g) == 1]
print(f"    {len(unsure)}/{len(groups)} visits fully unsure; {len(single)} visits have a single shot")

print("A3  error propagation: a confident-but-WRONG sibling carried onto its partner")
conf_wrong = [i for i in col if col[i]["x0"] and float(col[i]["score"]) >= CONF_TH and not is_hit(col[i], pt[i])]
used = [(i, int(m3[i]["cue"].split(":")[1])) for i in m3 if m3[i]["cue"].startswith("sibling")]
bad = [(i, j) for i, j in used if j in conf_wrong]
print(f"    confident-but-wrong colour finds: {len(conf_wrong)} {conf_wrong}")
print(f"    transfers made: {used}; from a wrong sibling: {bad}")
pairs = [(i, j) for g in groups.values() for i in g for j in g if i != j and j in conf_wrong and float(col[i]["score"] or 0) < CONF_TH]
print(f"    potential exposure (unsure photo whose confident sibling is wrong): {pairs}")

print("A4  colour check accepting a different object near the carried point")
fv = [i for i in m3 if m3[i]["state"] == "found-visible"]
print(f"    found-visible after transfer: {[(i, 'hit' if is_hit(m3[i], pt[i]) else 'MISS') for i in fv]}")
lc = [i for i in m3 if m3[i]["state"] == "located-covered"]
print(f"    located-covered: {[(i, 'hit' if is_hit(m3[i], pt[i]) else 'MISS') for i in lc]}")

print("A5  robustness: perturb clear+partial photos and re-run the colour locator (stage 1 of method 3)")
ids = [i for i in sorted(ph) if ph[i][1] != "3_hard"][::2]
def jpeg(im, q):
    return cv2.imdecode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q])[1], 1)
def hue(im, d):
    h = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); h[..., 0] = (h[..., 0].astype(int) + d) % 180
    return cv2.cvtColor(h, cv2.COLOR_HSV2BGR)
ATT = {
    "none": lambda im: im,
    "dark x0.6 (evening)": lambda im: cv2.convertScaleAbs(im, alpha=0.6),
    "bright x1.4 (noon glare)": lambda im: cv2.convertScaleAbs(im, alpha=1.4),
    "blur 7px (motion/focus)": lambda im: cv2.GaussianBlur(im, (0, 0), 3.5),
    "jpeg q25 (compression)": lambda im: jpeg(im, 25),
    "hue +6 (white balance)": lambda im: hue(im, 6),
    "hue -6 (white balance)": lambda im: hue(im, -6),
    "half size (higher flight)": lambda im: cv2.resize(cv2.resize(im, None, fx=0.5, fy=0.5), (im.shape[1], im.shape[0])),
}
t = time.time()
for name, f in ATT.items():
    hits = 0
    for i in ids:
        img, sc = load(ph[i][0])
        r = locate(f(img))
        if r["box"] is not None:
            b = [round(v / sc) for v in r["box"]]
            hits += is_hit({"x0": b[0], "y0": b[1], "x1": b[2], "y1": b[3]}, pt[i])
    print(f"    {name:26s} found {hits}/{len(ids)} = {hits / len(ids):.3f}")
print(f"    ({time.time() - t:.0f}s)")
print("RESULT PASS (loophole hunt completed; findings above)")
