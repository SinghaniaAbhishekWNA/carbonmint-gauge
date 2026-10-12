"""Contact sheet of detections (debug): each tile = a 900x900 window around the detected stack, box drawn."""
import csv, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, ".")
from gauge.detect import load, detect, box

rows = list(csv.DictReader(open("data/index.csv")))
only = [int(a) for a in sys.argv[2:]]
rows = [r for i, r in enumerate(rows) if not only or i in only]
names = sorted(only) or list(range(len(rows)))
tiles = []
for r in rows:
    im = load("way points/" + r["photo"])
    det = detect(im)
    pil = Image.fromarray(im.astype(np.uint8))
    if det is None:
        t = pil.resize((300, 225)); tiles.append((t, r["photo"], "NONE")); continue
    c = det["center"]; L = det["t1"] - det["t0"]; S = max(300, int(L * 1.5))
    x0, y0 = int(c[0] - S / 2), int(c[1] - S / 2)
    t = pil.crop((x0, y0, x0 + S, y0 + S))
    dr = ImageDraw.Draw(t)
    b = box(det) - [x0, y0]
    dr.polygon([tuple(p) for p in b], outline=(0, 255, 255), width=max(2, S // 150))
    tiles.append((t.resize((300, 300)), r["photo"], f"r{det['red_px']} g{det['grey_px']} L{int(L)}"))
cols = 8
for k in range(0, len(tiles), 32):
    chunk = tiles[k:k + 32]
    sheet = Image.new("RGB", (cols * 300, ((len(chunk) + cols - 1) // cols) * 320), "white")
    d = ImageDraw.Draw(sheet)
    for i, (t, name, lab) in enumerate(chunk):
        x, y = (i % cols) * 300, (i // cols) * 320
        sheet.paste(t, (x, y)); d.text((x + 3, y + 302), f"{names[k+i]} {lab}", fill="black")
    sheet.save(f"{sys.argv[1]}/det_{k//32}.jpg", quality=85)
