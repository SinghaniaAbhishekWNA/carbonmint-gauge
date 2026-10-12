"""Method 3: align-and-transfer, then lid/colour refine.

Align today's photo to a reference shot of the same checkpoint from ANOTHER day in which the colour
locator found the gauge confidently (never the hand key, never the same day). SIFT features on rigid,
non-vegetation pixels (soil, bund, lid, cylinder) + RANSAC homography; carry the reference gauge point
across. Abstain when the alignment is weak.

python pipeline/align.py measure        transfer error vs the hand key, per set (alignment only)
"""
import csv, pathlib, sys, time
import cv2, numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from isolate import ROOT, photos, points
from locate import CONF_TH, visits

ALIGN_W = 1600          # working width for feature matching
MIN_INLIERS = 25        # below this the alignment is not trusted -> abstain
RATIO = 0.75            # Lowe ratio test

_sift = cv2.SIFT_create(nfeatures=4000)
_cache = {}


def rigid_mask(img):
    """Non-vegetation pixels: soil, bund, lid, cylinder. Leaves move and grow between days."""
    h, s, v = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2HSV))
    veg = (h >= 22) & (h <= 95) & (s > 40)
    m = (~veg).astype(np.uint8) * 255
    return cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))


def features(i, path, use_mask=True):
    key = (i, use_mask)
    if key not in _cache:
        im = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
        sc = ALIGN_W / im.shape[1]
        small = cv2.resize(im, (ALIGN_W, round(im.shape[0] * sc)), interpolation=cv2.INTER_AREA)
        g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        kp, des = _sift.detectAndCompute(g, rigid_mask(small) if use_mask else None)
        _cache[key] = (np.float32([k.pt for k in kp]), des, sc)
    return _cache[key]


def homography(a, b):
    """H mapping points of photo a -> photo b (working px), and inlier count."""
    pa, da, _ = a
    pb, db, _ = b
    if da is None or db is None or len(da) < 10 or len(db) < 10:
        return None, 0
    m = cv2.BFMatcher(cv2.NORM_L2).knnMatch(da, db, k=2)
    good = [x[0] for x in m if len(x) == 2 and x[0].distance < RATIO * x[1].distance]
    if len(good) < 10:
        return None, 0
    src = pa[[g.queryIdx for g in good]]
    dst = pb[[g.trainIdx for g in good]]
    H, inl = cv2.findHomography(src, dst, cv2.RANSAC, 6.0)
    if H is None:
        return None, 0
    return H, int(inl.sum())


def references():
    """{idx: (x, y)} gauge points from the colour locator's confident finds (bottom-centre of the box)."""
    col = {int(r["idx"]): r for r in csv.DictReader(open(ROOT / "results/locate_colour.csv"))}
    return {i: ((int(r["x0"]) + int(r["x1"])) / 2, float(r["y1"])) for i, r in col.items()
            if r["x0"] and float(r["score"]) >= CONF_TH}


def transfer(i, ph, vis, refs, use_mask=True):
    """Best other-day reference for photo i -> (x, y) full-res, inliers, ref idx; or None when abstaining."""
    tgt = features(i, ph[i][0], use_mask)
    best = None
    for j, pt in refs.items():
        if j == i or vis[j][0] != vis[i][0] or vis[j][1] == vis[i][1]:
            continue
        ref = features(j, ph[j][0], use_mask)
        H, n = homography(ref, tgt)
        if H is None or (best and n <= best[1]):
            continue
        p = np.float32([[[pt[0] * ref[2], pt[1] * ref[2]]]])
        q = cv2.perspectiveTransform(p, H)[0, 0] / tgt[2]
        best = ((float(q[0]), float(q[1])), n, j)
    if best is None or best[1] < MIN_INLIERS:
        return None, (best[1] if best else 0), (best[2] if best else None)
    return best


def measure(use_mask=True):
    t = time.time()
    ph, pt, vis, refs = photos(), points(), visits(), references()
    rows = []
    for i in sorted(ph):
        res = transfer(i, ph, vis, refs, use_mask)
        if res[0] is None:
            rows.append((i, ph[i][1], "", "", res[1], res[2], ""))
            continue
        (x, y), n, j = res
        err = float(np.hypot(x - pt[i][0], y - pt[i][1]))
        rows.append((i, ph[i][1], round(x), round(y), n, j, round(err)))
    tag = "masked" if use_mask else "full"
    with open(ROOT / f"results/align_{tag}.csv", "w", newline="") as fh:
        csv.writer(fh).writerows([("idx", "class", "x", "y", "inliers", "ref", "err_px"), *rows])
    print(f"alignment ({tag} features, min {MIN_INLIERS} inliers) in {time.time() - t:.0f}s")
    for s in ("1_clear", "2_partial", "3_hard"):
        sub = [r for r in rows if r[1] == s]
        e = np.array([r[6] for r in sub if r[6] != ""], float)
        print(f"  {s:9s}: aligned {len(e)}/{len(sub)}  median err {np.median(e) if len(e) else float('nan'):.0f} px  "
              f"within 100 px {np.mean(e <= 100) if len(e) else 0:.2f}  within 200 px {np.mean(e <= 200) if len(e) else 0:.2f}")
    return rows


if __name__ == "__main__":
    if sys.argv[1:2] == ["measure"]:
        measure(use_mask="--nomask" not in sys.argv)


# ---------------------------------------------------------------------------------------------
# Method 3 v2 "sibling transfer". Cross-day alignment failed (median 5 RANSAC inliers: the canopy
# changes too much between days). The two shots of ONE visit align well (median 500 inliers, 41 px).
# So: when a shot is unsure, align its confident sibling onto it, carry the gauge across, then
# verify with colour isolation in a small window around the carried point.
SIB_MIN_INLIERS = 60
REFINE_HALF = 300  # full-res px around the carried point searched by the colour locator


def sibling_transfer(base="colour"):
    from locate import locate, load
    if base.endswith("_wb"):
        import isolate as _iso
        _iso.PREPROCESS = _iso.normalize
    t = time.time()
    ph, vis = photos(), visits()
    col = {int(r["idx"]): r for r in csv.DictReader(open(ROOT / f"results/locate_{base}.csv"))}
    score = {i: float(r["score"] or 0) for i, r in col.items()}
    groups = {}
    for i, k in vis.items():
        groups.setdefault(k, []).append(i)
    rows = []
    for i in sorted(ph):
        r = dict(col[i]); r["state"] = "colour" if r["x0"] and score[i] >= CONF_TH else "colour-unsure"; r["inliers"] = ""
        sibs = [j for j in groups[vis[i]] if j != i and col[j]["x0"] and score[j] >= CONF_TH and score[j] > score[i]]
        if r["state"] == "colour-unsure" and sibs:
            j = max(sibs, key=lambda k: score[k])
            a, b = features(j, ph[j][0], False), features(i, ph[i][0], False)
            H, n = homography(a, b)
            if H is not None and n >= SIB_MIN_INLIERS:
                bx = [int(col[j][k]) for k in ("x0", "y0", "x1", "y1")]
                cs = np.float32([[[bx[0], bx[1]]], [[bx[2], bx[1]]], [[bx[0], bx[3]]], [[bx[2], bx[3]]]]) * a[2]
                q = cv2.perspectiveTransform(cs, H).reshape(-1, 2) / b[2]
                tb = [int(q[:, 0].min()), int(q[:, 1].min()), int(q[:, 0].max()), int(q[:, 1].max())]
                cx, cy = (tb[0] + tb[2]) / 2, tb[3]
                # colour check in a window around the carried gauge
                img, sc = load(ph[i][0])
                X0, Y0 = max(int((cx - REFINE_HALF) * sc), 0), max(int((tb[1] - REFINE_HALF) * sc), 0)
                X1, Y1 = int((cx + REFINE_HALF) * sc), int((cy + REFINE_HALF) * sc)
                sub = img[Y0:Y1, X0:X1]
                loc = locate(sub) if sub.size else {"box": None, "score": 0}
                if loc["box"] is not None and loc["score"] >= CONF_TH * 0.6:
                    lb = loc["box"]
                    r.update(x0=round((lb[0] + X0) / sc), y0=round((lb[1] + Y0) / sc), x1=round((lb[2] + X0) / sc),
                             y1=round((lb[3] + Y0) / sc), score=round(loc["score"], 4), state="found-visible")
                else:
                    r.update(x0=tb[0], y0=tb[1], x1=tb[2], y1=tb[3], state="located-covered")
                r["cue"] = f"sibling:{j}"; r["inliers"] = n
        rows.append(r)
    name = "method3" if base == "colour" else f"method3_{base}"
    with open(ROOT / f"results/locate_{name}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    from collections import Counter
    print(f"128 rows -> results/locate_{name}.csv in {time.time() - t:.0f}s; states {dict(Counter(r['state'] for r in rows))}")


if __name__ == "__main__" and sys.argv[1:2] == ["method3"]:
    sibling_transfer(sys.argv[2] if len(sys.argv) > 2 else "colour")


def combined(src="method3", out="method3plus"):
    """Method 3+: sibling transfer first; Gauge memory (hybrid) only for photos whose whole visit is unsure."""
    m3 = {int(r["idx"]): r for r in csv.DictReader(open(ROOT / f"results/locate_{src}.csv"))}
    hy = {int(r["idx"]): r for r in csv.DictReader(open(ROOT / "results/locate_hybrid.csv"))}
    rows = []
    for i in sorted(m3):
        r = m3[i]
        if r["state"] == "colour-unsure":
            r = {**r, **{k: hy[i][k] for k in ("x0", "y0", "x1", "y1", "score")}, "state": "memory", "cue": "memory:" + hy[i]["cue"]}
        rows.append(r)
    with open(ROOT / f"results/locate_{out}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"128 rows -> results/locate_{out}.csv")


if __name__ == "__main__" and sys.argv[1:2] == ["method3plus"]:
    combined()
if __name__ == "__main__" and sys.argv[1:2] == ["final"]:
    combined("method3_colour_wb", "method3final")
