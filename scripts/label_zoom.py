"""Labelling aid: tight, 3x-magnified straightened rod, split into rows of SEG full-image px, ruler in full-image y
(labels every 50 px). Nothing from the reader algorithm is drawn."""
import csv, json, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, "scripts")
from label_crops import MANUAL
from label_strips import axis, strip

SEG, W = 600, 1800


def span(k, photo, cand):
    if k in MANUAL or not cand[photo]:
        _, y0, y1 = MANUAL[k]
        return y0, y1
    c = cand[photo][0]
    L = c["t1"] - c["t0"]
    return c["center"][1] + c["t0"] - 0.25 * L - 60, c["center"][1] + c["t1"] + 0.25 * L + 60


if __name__ == "__main__":
    out, ks = sys.argv[1], [int(a) for a in sys.argv[2:]]
    rows = list(csv.DictReader(open("data/index.csv")))
    cand = json.load(open("data/candidates.json"))
    for k in ks:
        photo = rows[k]["photo"]
        im = np.asarray(Image.open("way points/" + photo).convert("RGB")).astype(float)
        p, d, half = axis(k, photo, cand)
        y0, y1 = span(k, photo, cand)
        y0, y1 = max(0, y0), min(3071, y1)
        segs = [(a, min(a + SEG, y1)) for a in np.arange(y0, y1, SEG)]
        sc = W / SEG
        rowh = int(3.2 * half * sc * 0.75) + 40
        sheet = Image.new("RGB", (W + 20, len(segs) * rowh + 20), "white")
        dr = ImageDraw.Draw(sheet)
        dr.text((10, 2), f"#{k} {photo[-40:]}", fill="black")
        for i, (a, b) in enumerate(segs):
            st, ys = strip(im, p, d, half * 0.75, a, b)
            w = int(len(ys) * sc)
            yy = 14 + i * rowh
            sheet.paste(st.resize((w, rowh - 40)), (10, yy))
            for j, yv in enumerate(ys):
                r = int(round(yv))
                if r % 10: continue
                x = 10 + j * sc
                big = r % 50 == 0
                dr.line([(x, yy + rowh - 40), (x, yy + rowh - 40 + (12 if big else 5))], fill="black")
                if big: dr.text((x - 12, yy + rowh - 24), str(r), fill="black")
        sheet.save(f"{out}/z_{k:03d}.jpg", quality=90)
