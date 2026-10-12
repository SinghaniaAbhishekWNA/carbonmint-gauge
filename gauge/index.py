"""P0.1.1 Index every photo: plot, visit, shot, GPS, altitude, gimbal angles (EXIF + DJI XMP).
Usage: python -m gauge.index "way points"  ->  data/index.csv"""
import csv, re, sys
from pathlib import Path
from PIL import Image

XMP = ("GpsLatitude", "GpsLongitude", "RelativeAltitude", "GimbalPitchDegree", "GimbalYawDegree")
COLS = ["photo", "plot", "visit", "date", "shot", "width", "height", "taken", *XMP]


def xmp(path):
    b = Path(path).read_bytes()
    i, j = b.find(b"<x:xmpmeta"), b.find(b"</x:xmpmeta>")
    return dict(re.findall(r'drone-dji:(\w+)="([^"]*)"', b[i:j].decode("utf8", "replace"))) if i >= 0 else {}


def rows(root):
    root = Path(root)
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        plot, stamp = folder.name.rsplit(" - ", 1)            # "...CKP K26 VP", "011026100546" = ddmmyy hhmmss
        date = f"20{stamp[4:6]}-{stamp[2:4]}-{stamp[0:2]}"
        for shot, f in enumerate(sorted(folder.glob("*.jpg")), 1):
            im = Image.open(f)
            x = xmp(f)
            yield dict(photo=f.relative_to(root).as_posix(), plot="-".join(plot.split("-")[:4]), visit=folder.name, date=date,
                       shot=shot, width=im.width, height=im.height, taken=im.getexif().get(306, ""),
                       **{k: x.get(k, "").lstrip("+") for k in XMP})


def main(root="way points", out="data/index.csv"):
    data = list(rows(root))
    Path(out).parent.mkdir(exist_ok=True)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, COLS); w.writeheader(); w.writerows(data)
    print(f"{len(data)} photos, {len({r['plot'] for r in data})} plots, {len({r['visit'] for r in data})} visits,"
          f" {sum(not r['GimbalPitchDegree'] for r in data)} missing gimbal pitch -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
