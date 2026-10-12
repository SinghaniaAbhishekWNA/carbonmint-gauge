"""Run v0 (company detector, rebuilt) on every photo -> data/v0_reads.csv."""
import csv, sys
from multiprocessing import Pool
sys.path.insert(0, ".")
from gauge.detect import load
from gauge import v0


def one(args):
    r, mag = args
    v0.MAGENTA_HUE = mag
    o = v0.read(load("way points/" + r["photo"]).astype("uint8"))
    return dict(photo=r["photo"], **{k: o[k] for k in ("cm", "confidence", "stripes", "hidden", "column_x", "accepted", "state")})


if __name__ == "__main__":
    # --magenta lo,hi tests the magenta-hue reading (default: the spec's literal 140,175 degrees)
    mag = tuple(int(x) for x in sys.argv[sys.argv.index("--magenta") + 1].split(",")) if "--magenta" in sys.argv else (140, 175)
    out = "data/v0_reads.csv" if mag == (140, 175) else f"data/v0_reads_mag{mag[0]}-{mag[1]}.csv"
    rows = list(csv.DictReader(open("data/index.csv")))
    with Pool(4) as p:
        res = p.map(one, [(r, mag) for r in rows])
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, list(res[0])); w.writeheader(); w.writerows(res)
    lab = {r["photo"]: float(r["rings"]) for r in csv.DictReader(open("data/labels.csv"))}
    n = len(res); acc = [r for r in res if r["accepted"]]
    ex = lambda r: r["cm"] is not None and r["cm"] == lab[r["photo"]]
    print(f"v0 magenta {mag}: accepted {len(acc)}/{n}; accepted & exact {sum(map(ex, acc))}/{n}; exact overall {sum(map(ex, res))}/{n}; "
          f"within1 {sum(r['cm'] is not None and abs(r['cm'] - lab[r['photo']]) <= 1 for r in res)}/{n}; no reading {sum(r['cm'] is None for r in res)}")
