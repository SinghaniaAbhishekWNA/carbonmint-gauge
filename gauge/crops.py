"""P1.1.1 Full-resolution rod crop per photo -> data/crops/<photo stem>.jpg; data/crops/missing.txt lists photos
with no rod found. Uses the detections in data/photo_reads.csv (run python -m gauge.run first)."""
import csv, sys
from pathlib import Path
from PIL import Image


def main(root="way points", reads="data/photo_reads.csv", out="data/crops"):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    missing, n = [], 0
    for r in csv.DictReader(open(reads)):
        if r["cx"] == "":
            missing.append(r["photo"]); continue
        cx, cy, h = float(r["cx"]), float(r["cy"]), float(r["half"])
        t0, t1, dy = float(r["t0"]), float(r["t1"]), float(r["dy"])
        L = t1 - t0
        y0, y1 = cy + (t0 - 0.6 * L - 80) * dy, cy + (t1 + 0.5 * L + 150) * dy
        w = max(6 * h, 0.35 * (y1 - y0))
        im = Image.open(Path(root) / r["photo"])
        im.crop((int(max(0, cx - w / 2)), int(max(0, y0)), int(min(im.width, cx + w / 2)), int(min(im.height, y1)))) \
          .save(out / (Path(r["photo"]).stem + ".jpg"), quality=90)
        n += 1
    (out / "missing.txt").write_text("\n".join(missing) + ("\n" if missing else ""))
    print(f"{n} crops, {len(missing)} with no rod found -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
