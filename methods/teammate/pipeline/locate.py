"""P1.2 locate the gauge from the colour masks (team idea), plus the P5 'Gauge memory' extras.

Colour-only: weighted cue map (red rings, blue-grey PVC, elongated black sleeve) -> best tall thin window
by local contrast (inside density minus surrounding density), scanned at a few stem sizes.

python pipeline/locate.py [--method colour|shape|hybrid]   writes results/locate_<method>.csv
"""
import csv, pathlib, sys, time
import cv2, numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from isolate import ROOT, isolate, load, photos

CUE_W = {"red": 1.0, "grey": 0.6, "black": 0.35}
CONF_TH = 0.30  # chosen on clear+partial only (precision ~0.91 at any threshold 0.2-0.4: the score is weakly informative)
# stem window sizes in working px (1000 px wide frame): narrow/medium/wide x short/medium/tall stems
SIZES = [(w, h) for w in (10, 18, 30) for h in (50, 120, 260)]


def elongated(mask, min_h=15, min_ratio=2.5):
    """Keep only components that are taller than wide (stems, sleeves); drops shadow blobs and leaf speckle."""
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    keep = np.zeros(n, bool)
    keep[1:] = (st[1:, cv2.CC_STAT_HEIGHT] >= min_h) & (st[1:, cv2.CC_STAT_HEIGHT] >= min_ratio * st[1:, cv2.CC_STAT_WIDTH])
    return keep[lab]


def cue_map(masks):
    # grey and black only count as thin upright parts (stem top, sleeve): the wide cylinder body and
    # canopy shadow otherwise outscore the stem
    return (CUE_W["red"] * masks["red"] + CUE_W["grey"] * elongated(masks["grey"], min_ratio=1.5)
            + CUE_W["black"] * elongated(masks["black"])).astype(np.float32)


def stem_map(img):
    """Looser 'anything stem-like' map for following the stem: includes rings darkened to maroon in shade."""
    h, s, v = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2HSV))
    dark_red = ((h < 12) | (h > 150)) & (s > 40) & (v > 25)
    pvc = (h >= 92) & (h <= 128) & (s <= 135) & (v >= 55)
    return (dark_red | pvc).astype(np.float32)


def shape_map(img):
    """P5.1.1 shape cue, v2. v1 (long straight vertical edges) failed: rice leaves are long and vertical too,
    and the ring stripes break the stem's own edges (0% on every set).
    v2: tall, upright, NON-GREEN structures at least ~5 px wide: the stem, grey top and sleeve qualify;
    green leaves are excluded by colour and thin shadow slivers by the width test."""
    h, s, v = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2HSV))
    nonveg = (~((h >= 22) & (h <= 95) & (s > 40)) & (v > 12)).astype(np.uint8)
    tall = cv2.morphologyEx(nonveg, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 31)))
    wide = cv2.morphologyEx(nonveg, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1)))
    m = tall & wide
    return elongated(m.astype(bool), min_h=25, min_ratio=3.0).astype(np.float32)


def best_window(score):
    """Scan tall thin windows; return (box, contrast) with box = (x0, y0, x1, y1) in working px."""
    H, W = score.shape
    ii = cv2.integral(score)
    def mean(x0, y0, x1, y1):
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
        a = (x1 - x0) * (y1 - y0)
        return (ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]) / a if a > 0 else 0.0
    best = (None, -1.0)
    for w, h in SIZES:
        ys, xs = np.mgrid[0:H - h:max(h // 6, 4), 0:W - w:max(w // 3, 2)]
        for y, x in zip(ys.ravel(), xs.ravel()):
            inside = mean(x, y, x + w, y + h)
            if inside < 0.15:
                continue
            ring = mean(x - 2 * w, y - h // 3, x + 3 * w, y + h + h // 3)
            c = inside - ring
            if c > best[1]:
                best = ((x, y, x + w, y + h), c)
    return best


def grow(win, score, masks, gap=45, on=0.12):
    """Follow the stem up and down its column from the best window, bridging leaf gaps up to `gap` px,
    then take in the sleeve top (dark band directly below the stem)."""
    x0, y0, x1, y1 = win
    H = score.shape[0]
    prof = cv2.blur(score[:, x0:x1].mean(axis=1, keepdims=True), (1, 9)).ravel()
    def walk(y, step):
        last = y
        while 0 <= y + step < H and abs(y + step - last) <= gap:
            y += step
            if prof[y] > on:
                last = y
        return last
    top, bot = walk(y0, -1), walk(y1 - 1, 1)
    dark = masks["black"][:, x0:x1].mean(axis=1)
    y = bot
    while y + 1 < H and y - bot < 60 and dark[y + 1] > 0.4:  # sleeve
        y += 1
    w = x1 - x0
    return (x0 - w, top - 5, x1 + w, min(max(y, bot) + 15, H))


def locate(img, method="colour", prior=None):
    """Return dict(box, score, cue). prior = (x, y, sigma) in working px for the hybrid method."""
    masks, _ = isolate(img)
    score = cue_map(masks)
    if method in ("shape", "hybrid", "colshape"):
        sh = shape_map(img)
        score = sh if method == "shape" else score + 0.5 * sh
    if method in ("hybrid", "colmem") and prior is not None:
        H, W = score.shape
        yy, xx = np.mgrid[0:H, 0:W]
        px, py, sig = prior
        score = score * (0.35 + np.exp(-((xx - px) ** 2 + (yy - py) ** 2) / (2 * sig ** 2)))
    win, c = best_window(score)
    if win is None:
        return {"box": None, "score": 0.0, "cue": "none"}
    x0, y0, x1, y1 = win
    share = {n: masks[n][y0:y1, x0:x1].mean() for n in ("red", "grey", "black")}
    follow = np.maximum(score, stem_map(img))
    return {"box": grow(win, follow, masks), "score": float(c), "cue": max(share, key=share.get)}


def visits():
    """{idx: (checkpoint, date)} from the folder names, e.g. '...CKP K26 SD - 011026100902' -> ('...CKP K26 SD', '011026')."""
    out = {}
    for r in csv.DictReader(open(ROOT / "sorted/visibility_labels.csv", encoding="utf-8")):
        cp, ts = r["checkpoint_folder"].rsplit(" - ", 1)
        out[int(r["idx"])] = (cp.strip(), ts[:6])
    return out


def memory_priors():
    """P5.1.2 leave-one-day-out prior: for each photo, where the gauge was confidently found by the colour
    method on OTHER days at the same checkpoint (never today's answer, never the hand-made key).
    Returns {idx: (x, y, sigma) in full-res px} or no entry when no other day had a confident find."""
    col = {int(r["idx"]): r for r in csv.DictReader(open(ROOT / "results/locate_colour.csv"))}
    vis = visits()
    finds = {i: ((int(r["x0"]) + int(r["x1"])) / 2, float(r["y1"])) for i, r in col.items()
             if r["x0"] and float(r["score"]) >= CONF_TH}
    pri = {}
    for i, (cp, day) in vis.items():
        pts = np.array([finds[j] for j in finds if vis[j][0] == cp and vis[j][1] != day])
        if len(pts):
            spread = float(np.median(np.abs(pts - np.median(pts, axis=0))))
            pri[i] = (*np.median(pts, axis=0), max(250.0, 2.5 * spread))
    return pri


def run(method="colour"):
    t = time.time()
    out = ROOT / f"results/locate_{method}.csv"
    rows = []
    pri = memory_priors() if method in ("hybrid", "colmem") else {}
    for i, (p, cls) in sorted(photos().items()):
        img, sc = load(p)
        prior = tuple(v * sc for v in pri[i]) if i in pri else None
        r = locate(img, method, prior)
        b = [round(v / sc) for v in r["box"]] if r["box"] else ["", "", "", ""]
        rows.append((i, cls, *b, round(r["score"], 4), r["cue"]))
    with open(out, "w", newline="") as fh:
        csv.writer(fh).writerows([("idx", "class", "x0", "y0", "x1", "y1", "score", "cue"), *rows])
    print(f"{len(rows)} rows -> {out.relative_to(ROOT)} in {time.time() - t:.1f}s")
    return out


def cascade():
    """Gauge memory as a fallback: keep the colour result when it is confident (score >= CONF_TH);
    otherwise use colour + shape + day-to-day memory. Chosen from the clear/partial ablation, where
    memory and shape hurt photos that colour already handled (framing drifts ~290 px between flights)."""
    col = {int(r["idx"]): r for r in csv.DictReader(open(ROOT / "results/locate_colour.csv"))}
    hyb = {int(r["idx"]): r for r in csv.DictReader(open(ROOT / "results/locate_hybrid.csv"))}
    rows = [col[i] if col[i]["x0"] and float(col[i]["score"]) >= CONF_TH else {**hyb[i], "cue": "memory:" + hyb[i]["cue"]}
            for i in sorted(col)]
    out = ROOT / "results/locate_cascade.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} rows -> {out.relative_to(ROOT)}; fallback used on {sum(r['cue'].startswith('memory') for r in rows)}")


if __name__ == "__main__":
    if "--wb" in sys.argv:  # method 3 colour constancy; output files get a _wb suffix
        import isolate as _iso
        _iso.PREPROCESS = _iso.normalize
        _run = run
        def run(method="colour"):
            src = _run(method)
            dst = src.with_name(src.stem + "_wb.csv"); dst.unlink(missing_ok=True); src.rename(dst)
            print("->", dst.relative_to(ROOT))
    m = sys.argv[sys.argv.index("--method") + 1] if "--method" in sys.argv else "colour"
    cascade() if m == "cascade" else run(m)
