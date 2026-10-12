"""Labelling aid: overview sheets with a 256-px grid (labels every 512 px) and the detector box, 9 photos per sheet."""
import csv, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, ".")
import json
from gauge.detect import load, box
cand = json.load(open('data/candidates.json'))

out = sys.argv[1]
rows = list(csv.DictReader(open("data/index.csv")))
F = 6  # downscale factor
W, H = 4096 // F, 3072 // F
for s in range(0, len(rows), 9):
    sheet = Image.new("RGB", (3 * W, 3 * (H + 18)), "white")
    d = ImageDraw.Draw(sheet)
    for i, r in enumerate(rows[s:s + 9]):
        im = load("way points/" + r["photo"])
        cs = cand[r['photo']]
        det = {k: np.array(v) if isinstance(v, list) else v for k, v in cs[0].items()} if cs else None
        t = Image.fromarray(im.astype(np.uint8)).resize((W, H))
        td = ImageDraw.Draw(t)
        for g in range(0, 4096, 256):
            td.line([(g / F, 0), (g / F, H)], fill=(255, 255, 255) if g % 512 == 0 else (150, 150, 150), width=1)
            if g % 512 == 0: td.text((g / F + 2, 2), str(g), fill="yellow")
        for g in range(0, 3072, 256):
            td.line([(0, g / F), (W, g / F)], fill=(255, 255, 255) if g % 512 == 0 else (150, 150, 150), width=1)
            if g % 512 == 0: td.text((2, g / F + 2), str(g), fill="yellow")
        if det:
            td.polygon([tuple(p / F) for p in box(det)], outline=(255, 0, 255), width=2)
        x, y = (i % 3) * W, (i // 3) * (H + 18)
        sheet.paste(t, (x, y)); d.text((x + 4, y + H + 3), f"#{s+i} {r['visit'][-13:]} shot{r['shot']}", fill="black")
    sheet.save(f"{out}/ov_{s//9:02d}.jpg", quality=88)
