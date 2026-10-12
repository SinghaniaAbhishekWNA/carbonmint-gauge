"""P1.1.3 Human spot-check of the silver labels. Picks 15 photos with a fixed seed, writes data/spotcheck.jpg
(each crop with Claude's ring count), then asks for a verdict per photo and saves data/spotcheck.csv.
Usage: python -m gauge.spotcheck            (interactive, ~5 minutes)
       python -m gauge.spotcheck --sheet    (only write the contact sheet)
       python -m gauge.spotcheck --round 2 --sheet   (a fresh 15, none from earlier rounds)
       python -m gauge.spotcheck --answers "y,y,12,y,..."   (15 verdicts given elsewhere: y = agree, or the count)"""
import csv, random, sys
from pathlib import Path
from PIL import Image, ImageDraw

SEED, N = 20261010, 15


ROUND = int(sys.argv[sys.argv.index("--round") + 1]) if "--round" in sys.argv else 1
TAG = "" if ROUND == 1 else f"_r{ROUND}"


def pick():
    """Round 1 uses SEED; later rounds use SEED + round - 1 and skip photos already checked in earlier rounds."""
    with open("data/labels.csv", newline="") as fh:
        lab = list(csv.DictReader(fh))
    seen = set()
    for r in range(1, ROUND):
        f = Path(f"data/spotcheck{'' if r == 1 else f'_r{r}'}.csv")
        if f.exists():
            with open(f, newline="") as fh:
                seen |= {x["photo"] for x in csv.DictReader(fh)}
    return random.Random(SEED + ROUND - 1).sample([r for r in lab if r["photo"] not in seen], N)


def sheet(rows, out=None):
    out = out or f"data/spotcheck{TAG}.jpg"
    tiles = []
    for i, r in enumerate(rows, 1):
        f = Path("data/crops") / (Path(r["photo"]).stem + ".jpg")
        im = Image.open(f) if f.exists() else Image.new("RGB", (300, 600), "grey")
        im.thumbnail((300, 600))
        t = Image.new("RGB", (300, 640), "white"); t.paste(im, (0, 0))
        ImageDraw.Draw(t).text((4, 606), f"{i}. Claude: {r['rings']} rings", fill="black")
        tiles.append(t)
    s = Image.new("RGB", (5 * 300, 3 * 640), "white")
    for i, t in enumerate(tiles):
        s.paste(t, ((i % 5) * 300, (i // 5) * 640))
    s.save(out, quality=90)
    return out


def main():
    rows = pick()
    print("Contact sheet:", sheet(rows))
    if "--sheet" in sys.argv:
        return
    given = None
    if "--answers" in sys.argv:
        given = [a.strip().lower() for a in sys.argv[sys.argv.index("--answers") + 1].split(",")]
        if len(given) != N:
            sys.exit(f"need {N} answers, got {len(given)}")
    res = []
    for i, r in enumerate(rows, 1):
        a = given[i - 1] if given else input(f"{i}. {r['photo'][-40:]}  Claude says {r['rings']} rings. Enter = agree, or type your count: ").strip()
        a = "" if a in ("y", "yes", "ok") else a
        res.append(dict(photo=r["photo"], claude=r["rings"], human=a or r["rings"], agree=int(not a or float(a) == float(r["rings"]))))
    with open(f"data/spotcheck{TAG}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, ["photo", "claude", "human", "agree"]); w.writeheader(); w.writerows(res)
    k = sum(x["agree"] for x in res)
    print(f"agreement {k}/{N} -> {'OK, labels stand' if k >= 14 else 'below 14/15: redo the labels before claiming accuracy'}")


if __name__ == "__main__":
    main()
