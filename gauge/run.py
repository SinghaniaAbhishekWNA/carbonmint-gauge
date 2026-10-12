"""Read every photo once (parallel) -> data/photo_reads_v2.csv (data/photo_reads.csv is the frozen v1 run).
Usage: python -m gauge.run ["way points"]"""
import csv, json, sys
from multiprocessing import Pool
from pathlib import Path
from .detect import load, detect, ring_mask
from .measure import read
from . import index

COLS = ["photo", "plot", "visit", "date", "shot", "rings", "naive", "pitch_px", "first_y", "last_y", "sleeve_y", "top_y",
        "cap_ratio", "confidence", "rod_len_px", "strength", "seen", "peaks", "sharp", "ringfrac", "cx", "cy", "half", "dx", "dy", "t0", "t1"]


def naive_count(im, det):
    """Baseline: count ring blobs that span >= 70% of the rod width (a plain counter, what a quick script would do)."""
    import numpy as np
    from scipy import ndimage as ndi
    from .measure import straighten
    L = det["t1"] - det["t0"]
    core, _ = straighten(im, det, 0.6 * L + 80, 0.5 * L + 150)
    full = ring_mask(core).mean(1) >= 0.7
    return int(ndi.label(full)[1])


def one(args):
    root, row = args
    im = load(Path(root) / row["photo"])
    det = detect(im)
    out = dict(row)
    if det is None:
        out.update(rings="", naive="", confidence=0)
        return out
    r = read(im, det)
    out.update({k: ("" if v is None else v) for k, v in r.items() if k in COLS})
    out.update(naive=naive_count(im, det), cx=round(det["center"][0], 1), cy=round(det["center"][1], 1),
               half=round(det["half"], 1), dx=round(det["dir"][0], 4), dy=round(det["dir"][1], 4),
               t0=round(det["t0"], 1), t1=round(det["t1"], 1))
    return out


def run(root="way points", out="data/photo_reads_v2.csv"):
    rows = list(index.rows(root))
    with Pool(6) as pool:
        res = pool.map(one, [(root, r) for r in rows])
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, COLS, extrasaction="ignore"); w.writeheader(); w.writerows(res)
    print(f"{len(res)} photos read, {sum(r['rings'] == '' for r in res)} with no rod found -> {out}")
    return res


if __name__ == "__main__":
    run(*sys.argv[1:])
