"""Answer-key check: build pipe_points.csv from hand-marked thumbnail points and draw review sheets.
python pipeline/truth_sheet.py [idx,idx,...]   (no args = all)"""
import csv, pathlib, sys, cv2, numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[1]
files = {int(r["idx"]): ROOT / "sorted" / r["class"] / f'{int(r["idx"]):03d}__{r["checkpoint_folder"].replace(" ", "_")}__{r["file"]}'
         for r in csv.DictReader(open(ROOT / "sorted/visibility_labels.csv", encoding="utf-8"))}
pts = {}
for line in open(ROOT / "data/pipe_points_thumb.txt", encoding="utf-8"):
    if line.strip() and not line.startswith("#"):
        p = line.split(); pts[int(p[0])] = (int(p[1]) / 640, int(p[2]) / 480, "unsure" if "?" in p[3:] else "sure")
want = [int(i) for i in sys.argv[1].split(",")] if len(sys.argv) > 1 else sorted(pts)
out, tiles = ROOT / "results/truth", []
out.mkdir(parents=True, exist_ok=True)
rows = []
for i in sorted(pts):
    im = cv2.imdecode(np.fromfile(str(files[i]), np.uint8), 1)
    H, W = im.shape[:2]; x, y = int(pts[i][0] * W), int(pts[i][1] * H)
    rows.append((i, x, y, pts[i][2]))
    if i in want:
        c = im[max(y - 700, 0):y + 700, max(x - 700, 0):x + 700].copy()
        cx, cy = x - max(x - 700, 0), y - max(y - 700, 0)
        cv2.circle(c, (cx, cy), 28, (255, 0, 255), 6)
        c = cv2.resize(c, (420, 420))
        cv2.putText(c, str(i), (6, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
        tiles.append(c)
with open(ROOT / "data/pipe_points.csv", "w", newline="") as fh:
    csv.writer(fh).writerows([("idx", "x", "y", "certainty"), *rows])
for k in range(0, len(tiles), 12):
    t = tiles[k:k + 12]; t += [np.zeros_like(tiles[0])] * (12 - len(t))
    cv2.imwrite(str(out / f"truth_{k:03d}.jpg"), np.vstack([np.hstack(t[r * 4:r * 4 + 4]) for r in range(3)]))
print(len(rows), "points;", len(tiles), "review tiles")
