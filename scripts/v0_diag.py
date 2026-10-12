"""Diagnostic only: which v0 rule holds it back on these photos? Runs v0 with one rule relaxed at a time."""
import csv, sys
from multiprocessing import Pool
sys.path.insert(0, ".")
from gauge.detect import load
from gauge import v0

VARIANTS = {"spec": {}, "value>=25": {"RED_V": 25}, "no thickness rule": {"THICK_OFF": True},
            "value>=25 + no thickness": {"RED_V": 25, "THICK_OFF": True}}


def one(args):
    r, name = args
    for k, v in VARIANTS[name].items():
        setattr(v0, k, v)
    if VARIANTS[name].get("THICK_OFF"):
        import numpy as np
        src = v0.read.__code__  # thickness rule disabled by widening the allowed bar height
        v0.THICK_LIMIT = 1e9
    o = v0.read(load("way points/" + r["photo"]).astype("uint8"))
    return r["photo"], o["cm"], o["accepted"]


if __name__ == "__main__":
    lab = {r["photo"]: float(r["rings"]) for r in csv.DictReader(open("data/labels.csv"))}
    rows = list(csv.DictReader(open("data/index.csv")))
    for name in VARIANTS:
        with Pool(4) as p:
            res = p.map(one, [(r, name) for r in rows])
        acc = [x for x in res if x[2]]
        print(f"{name:26s} accepted {len(acc):3d}  accepted&exact {sum(x[1] == lab[x[0]] for x in acc):3d}  "
              f"exact {sum(x[1] == lab[x[0]] for x in res):3d}  no reading {sum(x[1] is None for x in res):3d}  (of {len(res)})")
