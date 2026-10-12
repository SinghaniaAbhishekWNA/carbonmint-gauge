"""Labelling aid: for each photo, the top-4 detector candidates as crops + a thumbnail. Caches data/candidates.json."""
import csv, json, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, ".")
from gauge.detect import load, candidates

out = sys.argv[1]
rows = list(csv.DictReader(open("data/index.csv")))
cache = {}
T = 200
per = 12
for s in range(0, len(rows), per):
    sheet = Image.new("RGB", (5 * T, per * (T + 14)), "white")
    d = ImageDraw.Draw(sheet)
    for i, r in enumerate(rows[s:s + per]):
        k = s + i
        im = load("way points/" + r["photo"])
        cs = candidates(im)[:4]
        cache[r["photo"]] = [dict(center=c["center"].round(1).tolist(), dir=c["dir"].round(4).tolist(), half=round(c["half"], 1),
                                  t0=round(c["t0"], 1), t1=round(c["t1"], 1), red_px=c["red_px"], grey_px=c["grey_px"],
                                  score=round(c["score"])) for c in cs]
        pil = Image.fromarray(im.astype(np.uint8))
        y = i * (T + 14)
        th = pil.resize((T, T * 3 // 4)); td = ImageDraw.Draw(th)
        for j, c in enumerate(cs):
            cx, cy = c["center"] / 4096 * T
            td.text((cx, cy * 1.0 * 4096 / 3072 * 3 / 4 - 5), str(j), fill="magenta")
        sheet.paste(th, (0, y))
        for j, c in enumerate(cs):
            L = c["t1"] - c["t0"]; S = max(160, int(L * 1.3))
            x0, y0 = int(c["center"][0] - S / 2), int(c["center"][1] - S / 2)
            sheet.paste(pil.crop((x0, y0, x0 + S, y0 + S)).resize((T, T)), ((j + 1) * T, y))
            d.text(((j + 1) * T + 3, y + T + 1), f"c{j} r{c['red_px']} g{c['grey_px']}", fill="black")
        d.text((3, y + T + 1), f"#{k}", fill="black")
    sheet.save(f"{out}/cand_{s//per:02d}.jpg", quality=85)
json.dump(cache, open("data/candidates.json", "w"))
