"""Labelling aid v3: one row per photo = straightened rod (1 row, full span) + plotted redness profile
(median of R - max(G,B) across the rod core) + ruler in full-image y every 10 px, labels every 50.
A visual aid for counting bands by eye; no ring positions are computed or drawn."""
import csv, json, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, "scripts")
from label_strips import axis, strip
from label_zoom import span

W, IH, PH = 1880, 120, 90

if __name__ == "__main__":
    out, ks = sys.argv[1], [int(a) for a in sys.argv[2:]]
    rows = list(csv.DictReader(open("data/index.csv")))
    cand = json.load(open("data/candidates.json"))
    per = 4
    for s in range(0, len(ks), per):
        sheet = Image.new("RGB", (W + 40, per * (IH + PH + 50)), "white")
        dr = ImageDraw.Draw(sheet)
        for i, k in enumerate(ks[s:s + per]):
            photo = rows[k]["photo"]
            im = np.asarray(Image.open("way points/" + photo).convert("RGB")).astype(float)
            p, d, half = axis(k, photo, cand)
            y0, y1 = span(k, photo, cand)
            y0, y1 = max(0, y0), min(3071, y1)
            st, ys = strip(im, p, d, half * 0.6, y0, y1)
            a = np.asarray(st).astype(float)            # (width=S, height=T)? transposed: rows=S, cols=T
            core = a[a.shape[0] // 3: 2 * a.shape[0] // 3]
            red = np.median(core[..., 0] - np.maximum(core[..., 1], core[..., 2]), 0)
            sc = W / len(ys)
            yy = i * (IH + PH + 50)
            dr.text((20, yy), f"#{k} visit {rows[k]['visit'][-12:]} shot{rows[k]['shot']}", fill="black")
            sheet.paste(st.resize((W, IH)), (20, yy + 12))
            base = yy + 12 + IH + PH
            pts = [(20 + j * sc, base - np.clip(v, 0, 120) / 120 * PH) for j, v in enumerate(red)]
            dr.line([(20, base), (20 + W, base)], fill=(200, 200, 200))
            dr.line(pts, fill=(200, 0, 0), width=2)
            for j, yv in enumerate(ys):
                r = int(round(yv))
                if r % 10: continue
                x = 20 + j * sc
                big = r % 50 == 0
                dr.line([(x, base), (x, base + (10 if big else 4))], fill="black")
                if big and (r % 100 == 0 or sc > 1.2): dr.text((x - 10, base + 12), str(r), fill="black")
        sheet.save(f"{out}/p_{s//per:02d}.png")
