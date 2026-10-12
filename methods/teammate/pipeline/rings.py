"""P3 ring counting inside each located gauge box (full resolution).

counted : red bands down the centre of the stem
rhythm  : rings repeat at a fixed spacing, so (span from first to last band) / spacing + 1 also counts
          rings hidden by leaves in between (our 'ring rhythm reader')
state   : counted | dry (gauge found, no red bands: float down) | unreadable (no gauge box)

python pipeline/rings.py [--method colour|cascade]   -> results/rings_<method>.csv
"""
import csv, pathlib, sys
import cv2, numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from isolate import ROOT, photos

MIN_BAND, MIN_GAP = 3, 3  # px at full resolution
SCALE_MAX = 24            # rings on a fully raised stem (seen on every flooded gauge)
RHYTHM_FROM = 12          # gap-filling only on dense scales; on short stems a stray band skews the spacing


def red_rows(crop):
    h, s, v = cv2.split(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV))
    red = ((h < 12) | (h > 150)) & (s > 45) & (v > 35)
    W = red.shape[1]
    centre = red[:, int(W * 0.3):int(W * 0.7)]  # the box is stem +/- one stem width; read the middle
    return np.convolve(centre.mean(axis=1), np.ones(3) / 3, mode="same")


def bands(profile, th=0.3):
    on = profile > th
    runs, start = [], None
    for y, o in enumerate(on):
        if o and start is None:
            start = y
        elif not o and start is not None:
            if y - start >= MIN_BAND:
                runs.append((start, y))
            start = None
    if start is not None and len(on) - start >= MIN_BAND:
        runs.append((start, len(on)))
    merged = []
    for r in runs:  # bridge tiny breaks inside one ring
        if merged and r[0] - merged[-1][1] < MIN_GAP:
            merged[-1] = (merged[-1][0], r[1])
        else:
            merged.append(r)
    return merged


def read(img, box):
    x0, y0, x1, y1 = box
    crop = img[max(y0, 0):y1, max(x0, 0):x1]
    if crop.size == 0:
        return "unreadable", None, None
    b = bands(red_rows(crop))
    if not b:
        return "dry", 0, 0
    centres = np.array([(a + c) / 2 for a, c in b])
    counted = len(b)
    if counted >= 4:
        spacing = float(np.median(np.diff(centres)))
        rhythm = int(round((centres[-1] - centres[0]) / spacing)) + 1
    else:
        rhythm = counted
    final = min(rhythm, SCALE_MAX) if counted >= RHYTHM_FROM and rhythm <= SCALE_MAX + 2 else counted
    return "counted", counted, final


def run(method):
    loc = {int(r["idx"]): r for r in csv.DictReader(open(ROOT / f"results/locate_{method}.csv"))}
    rows = []
    for i, (p, cls) in sorted(photos().items()):
        r = loc[i]
        if not r["x0"]:
            rows.append((i, cls, "unreadable", "", ""))
            continue
        img = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
        st, c, rh = read(img, [int(r[k]) for k in ("x0", "y0", "x1", "y1")])
        rows.append((i, cls, st, "" if c is None else c, "" if rh is None else rh))
    out = ROOT / f"results/rings_{method}.csv"
    with open(out, "w", newline="") as fh:
        csv.writer(fh).writerows([("idx", "class", "state", "counted", "rings"), *rows])
    from collections import Counter
    print(f"{len(rows)} rows -> {out.relative_to(ROOT)}  states: {dict(Counter(r[2] for r in rows))}")
    located = sum(1 for r in loc.values() if r["x0"])
    ok = sum(1 for r in rows if r[2] != "unreadable" or not loc[r[0]]["x0"]) == len(rows)
    print(f"located boxes: {located}; every located box has a row with state counted/dry: {ok}")
    print("RESULT", "PASS" if ok and len(rows) == 128 else "FAIL")


if __name__ == "__main__":
    run(sys.argv[sys.argv.index("--method") + 1] if "--method" in sys.argv else "colour")
