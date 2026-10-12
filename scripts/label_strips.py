"""Labelling aid: straightened, enlarged rod strips laid horizontal (top of rod on the left), with a ruler in
full-image y. Read rod-top y, sleeve-edge y and count rings by eye. No algorithm output is drawn."""
import csv, json, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
sys.path.insert(0, "scripts")
from label_crops import window, MANUAL


def axis(k, photo, cand):
    """(point, unit dir down the rod, half-width) for sampling."""
    if k in MANUAL or not cand[photo]:
        cx, y0, y1 = MANUAL[k]
        return np.array([cx, (y0 + y1) / 2]), np.array([0.0, 1.0]), 60.0
    c = cand[photo][0]
    return np.array(c["center"]), np.array(c["dir"]), max(c["half"], 20.0)


def strip(im, p, d, half, y0, y1):
    n = np.array([-d[1], d[0]])
    t0, t1 = (y0 - p[1]) / d[1], (y1 - p[1]) / d[1]
    T = np.arange(t0, t1)
    S = np.arange(-2.2 * half, 2.2 * half)
    px = p[0] + T[:, None] * d[0] + S[None, :] * n[0]
    py = p[1] + T[:, None] * d[1] + S[None, :] * n[1]
    rgb = np.stack([ndi.map_coordinates(im[..., c], [py, px], order=1, mode="nearest") for c in range(3)], -1)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).transpose(Image.Transpose.TRANSPOSE), p[1] + T * d[1]


if __name__ == "__main__":
    out, only = sys.argv[1], [int(a) for a in sys.argv[2:]]
    rows = list(csv.DictReader(open("data/index.csv")))
    cand = json.load(open("data/candidates.json"))
    ks = only or list(range(len(rows)))
    W, H, PER = 1900, 150, 5
    for s in range(0, len(ks), PER):
        sheet = Image.new("RGB", (W + 20, PER * (H + 48)), "white")
        d = ImageDraw.Draw(sheet)
        for i, k in enumerate(ks[s:s + PER]):
            im = np.asarray(Image.open("way points/" + rows[k]["photo"]).convert("RGB")).astype(float)
            cx, y0, y1 = window(k, rows[k]["photo"], cand)
            y0, y1 = max(0, y0), min(3071, y1)
            p, dv, half = axis(k, rows[k]["photo"], cand)
            st, ys = strip(im, p, dv, half, y0, y1)
            L = len(ys); sc = W / L
            y = i * (H + 48)
            sheet.paste(st.resize((W, H)), (10, y + 18))
            step = 5 if L < 400 else 10 if L < 1000 else 20
            for j in range(0, L, 1):
                yy = ys[j]
                if int(round(yy)) % step: continue
                xx = 10 + j * sc
                big = int(round(yy)) % (step * 5) == 0
                d.line([(xx, y + H + 18), (xx, y + H + 18 + (12 if big else 5))], fill="black")
                if big: d.text((xx - 10, y + H + 32), str(int(round(yy))), fill="black")
            d.text((12, y + 2), f"#{k}  axis p={p.round(0).tolist()} d={dv.round(3).tolist()}  len={L}px", fill="black")
        sheet.save(f"{out}/st_{s//PER:02d}.jpg", quality=92)
