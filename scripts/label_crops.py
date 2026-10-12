"""Labelling aid: full-res rod crops with a y-ruler in full-image pixels, 4 photos per sheet.
Window per photo = detector candidate 0, or a manual (cx, y0, y1) override where the detector missed."""
import csv, json, sys
from PIL import Image, ImageDraw

MANUAL = {1: (1920, 600, 1500), 10: (1985, 900, 1900), 11: (2000, 900, 1900), 35: (2248, 650, 1300),
          72: (1950, 1000, 1900), 74: (2186, 350, 1350), 87: (1953, 1150, 1550), 89: (2174, 1000, 1700),
          90: (2106, 1300, 1700), 91: (2076, 650, 1500), 102: (2026, 400, 1800), 103: (2076, 850, 1950),
          104: (2198, 650, 1850), 109: (1953, 1000, 2100), 110: (1910, 1000, 2100), 113: (2125, 1000, 2200),
          114: (2150, 1100, 2400), 119: (2100, 900, 2300), 120: (2150, 900, 2300)}


def window(k, photo, cand):
    if k in MANUAL:
        return MANUAL[k]
    c = cand[photo][0]
    cx, cy = c["center"]
    L = c["t1"] - c["t0"]
    return cx, cy + c["t0"] - 0.6 * L - 150, cy + c["t1"] + 0.4 * L + 250


if __name__ == "__main__":
    out, only = sys.argv[1], [int(a) for a in sys.argv[2:]]
    rows = list(csv.DictReader(open("data/index.csv")))
    cand = json.load(open("data/candidates.json"))
    ks = only or list(range(len(rows)))
    json.dump({k: window(k, rows[k]["photo"], cand) for k in range(len(rows))}, open("data/windows.json", "w"))
    TH, TW, M = 1000, 420, 70
    for s in range(0, len(ks), 4):
        sheet = Image.new("RGB", (4 * (TW + M), TH + 20), "white")
        d = ImageDraw.Draw(sheet)
        for i, k in enumerate(ks[s:s + 4]):
            cx, y0, y1 = window(k, rows[k]["photo"], cand)
            y0, y1 = max(0, y0), min(3072, y1)
            h = y1 - y0; w = h * TW / TH
            im = Image.open("way points/" + rows[k]["photo"]).crop((int(cx - w / 2), int(y0), int(cx + w / 2), int(y1)))
            sc = TH / h
            x = i * (TW + M) + M
            sheet.paste(im.resize((TW, TH)), (x, 0))
            step = 10 if h < 500 else 25 if h < 1200 else 50
            for yy in range(int(y0) // step * step, int(y1) + 1, step):
                py = (yy - y0) * sc
                if py < 0: continue
                big = yy % (step * 4) == 0
                d.line([(x - (14 if big else 6), py), (x, py)], fill="black")
                if big: d.text((x - 50, py - 6), str(yy), fill="black")
            d.text((x, TH + 4), f"#{k} cx={int(cx)} x:{int(cx-w/2)}-{int(cx+w/2)}", fill="black")
        sheet.save(f"{out}/lab_{s//4:02d}.jpg", quality=92)
