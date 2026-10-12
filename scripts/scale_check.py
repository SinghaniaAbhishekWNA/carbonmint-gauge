"""Does the reader still work on a downscaled photo (browser-side resize before upload)? Exact-match rate vs scale."""
import csv, sys
from multiprocessing import Pool
import numpy as np
from PIL import Image
sys.path.insert(0, ".")
from gauge.detect import detect
from gauge.measure import read


def one(args):
    photo, width = args
    im = Image.open("way points/" + photo).convert("RGB")
    if width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    a = np.asarray(im).astype(np.int16)
    d = detect(a)
    return photo, (read(a, d)["rings"] if d else None)


if __name__ == "__main__":
    lab = {r["photo"]: float(r["rings"]) for r in csv.DictReader(open("data/labels.csv"))}
    for width in map(int, sys.argv[1:]):
        with Pool(5) as p:
            res = p.map(one, [(ph, width) for ph in lab])
        ex = sum(r == lab[ph] for ph, r in res)
        print(f"width {width or 'full'}: exact {ex}/{len(res)} = {100 * ex / len(res):.1f}%")
