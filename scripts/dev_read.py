"""Dev loop: read every cached photo in parallel, compare with silver labels, print misses."""
import csv, sys, json
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, ".")
from gauge.detect import detect
from gauge.measure import read


def one(k):
    im = np.load(f"data/cache/{k:03d}.npy").astype(np.int16)
    det = detect(im)
    return k, (read(im, det) if det else dict(rings=None, confidence=0)), \
        (None if det is None else dict(center=det["center"].tolist(), dir=det["dir"].tolist(), half=det["half"], t0=det["t0"], t1=det["t1"]))


if __name__ == "__main__":
    lab = list(csv.DictReader(open("data/labels.csv")))
    ks = [int(a) for a in sys.argv[1:]] or range(len(lab))
    with Pool(6) as pool:
        res = dict((k, (o, d)) for k, o, d in pool.map(one, ks))
    json.dump({k: v for k, v in res.items()}, open("data/dev_reads.json", "w"))
    ok = ok1 = 0
    for k in ks:
        o = res[k][0]; y = float(lab[k]["rings"]); p = o["rings"]
        e = None if p is None else p - y
        ok += e is not None and abs(e) < 0.5; ok1 += e is not None and abs(e) <= 1
        if e is None or abs(e) > 1:
            print("MISS", k, y, p, o.get("pitch_px"), o.get("confidence"), "first", o.get("first_y"), lab[k]["first_ring_y"],
                  "last", o.get("last_y"), lab[k]["last_ring_y"], "sleeve", o.get("sleeve_y"))
    print(f"exact {ok}/{len(ks)}  +-1 {ok1}/{len(ks)}")
