"""P2.1.2 miss gallery for the hard set: zoomed crops around each miss (box red, true point magenta)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import cv2, numpy as np
from evaluate import read_locate, is_hit, ROOT
from isolate import photos, points, load

REASON = {  # one-line cause per miss, from looking at each crop
    18: "wrong red object: a red/pink patch high in the canopy beat the half-hidden stem",
    90: "too far: wide shot, the gauge is ~30 px tall in the frame",
    102: "near miss: box on the stem top, the sleeve point is hidden lower down",
    110: "near miss: box on the dark sleeve edge beside the stem (stem hidden by seed heads)",
    111: "near miss: same as 110 on the second shot",
    113: "fully covered: no stem colour visible, only dark sleeve fragments",
    114: "fully covered: stem behind ripe panicles",
    115: "fully covered: stem behind ripe panicles",
    117: "near miss: box beside the sleeve",
    120: "fully covered: grey stem top only a few pixels, washed out",
    121: "fully covered: same as 120",
    124: "fully covered: pipe barely visible even to the eye (marked unsure)",
    125: "fully covered: same as 124 (marked unsure)",
    126: "visible lid + small grey top, but too small/short to pass the stem window",
    127: "same as 126",
}
loc, pt, ph = read_locate("colour"), points(), photos()
miss = [i for i in sorted(loc) if ph[i][1] == "3_hard" and not is_hit(loc[i], pt[i])]
tiles = []
for i in miss:
    img, sc = load(ph[i][0])
    x, y = int(pt[i][0] * sc), int(pt[i][1] * sc)
    r = loc[i]
    if r["x0"]:
        b = [int(int(r[k]) * sc) for k in ("x0", "y0", "x1", "y1")]
        cv2.rectangle(img, b[:2], b[2:], (0, 0, 255), 2)
    cv2.circle(img, (x, y), 8, (255, 0, 255), 2)
    c = img[max(y - 160, 0):y + 160, max(x - 160, 0):x + 160]
    c = cv2.resize(c, (360, 360))
    cv2.putText(c, str(i), (6, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
    tiles.append(c)
while len(tiles) % 5:
    tiles.append(np.zeros_like(tiles[0]))
cv2.imwrite(str(ROOT / "results/hard_misses.jpg"), np.vstack([np.hstack(tiles[k:k + 5]) for k in range(0, len(tiles), 5)]))
for i in miss:
    print(f"{i:3d}  {REASON.get(i, 'NO REASON WRITTEN')}")
ok = all(i in REASON for i in miss)
print(f"{len(miss)} misses, all with a reason" if ok else "some misses lack a reason")
print("RESULT", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
