"""Scoring against the hand-made answer key. Prints RESULT PASS/FAIL against the leaf's target and
writes a gallery image for the evidence screenshot.

python pipeline/evaluate.py locate --set clear|partial|hard|all [--method colour|shape|hybrid] [--target 0.95]
"""
import argparse, csv, pathlib, sys
import cv2, numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from isolate import ROOT, load, photos, points

SETS = {"clear": "1_clear", "partial": "2_partial", "hard": "3_hard"}


def read_locate(method):
    return {int(r["idx"]): r for r in csv.DictReader(open(ROOT / f"results/locate_{method}.csv"))}


def is_hit(r, pt, strict=False):
    """Found the gauge = box on the gauge's column, with the marked sleeve-top point inside it or directly
    below it within half the box height (leaves often hide the lowest part of the stem).
    strict = point must be inside the box."""
    if not r["x0"]:
        return False
    x0, y0, x1, y1 = (int(r[k]) for k in ("x0", "y0", "x1", "y1"))
    below = 0 if strict else (y1 - y0) // 2
    return x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1 + below


def gallery(idxs, loc, pt, name, per_row=6):
    ph, tiles = photos(), []
    for i in idxs:
        img, sc = load(ph[i][0])
        r = loc[i]
        hit = is_hit(r, pt[i])
        if r["x0"]:
            b = [int(int(r[k]) * sc) for k in ("x0", "y0", "x1", "y1")]
            cv2.rectangle(img, b[:2], b[2:], (0, 255, 0) if hit else (0, 0, 255), 4)
        cv2.circle(img, (int(pt[i][0] * sc), int(pt[i][1] * sc)), 9, (255, 0, 255), 3)
        cv2.putText(img, f"{i} {'HIT' if hit else 'MISS'} s={float(r['score']):.2f}", (10, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 255), 3)
        tiles.append(cv2.resize(img, (400, 300)))
    while len(tiles) % per_row:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[k:k + per_row]) for k in range(0, len(tiles), per_row)]
    cv2.imwrite(str(ROOT / f"results/{name}.jpg"), np.vstack(rows))


def cmd_locate(a):
    loc, pt, ph = read_locate(a.method), points(), photos()
    idxs = [i for i in sorted(loc) if a.set == "all" or ph[i][1] == SETS[a.set]]
    hits = [i for i in idxs if is_hit(loc[i], pt[i])]
    rate = len(hits) / len(idxs)
    strict = sum(is_hit(loc[i], pt[i], strict=True) for i in idxs)
    print(f"method={a.method} set={a.set}: {len(hits)}/{len(idxs)} hits, hit rate {rate:.3f}"
          f"   (strict point-in-box: {strict}/{len(idxs)} = {strict / len(idxs):.3f})")
    print("misses:", [i for i in idxs if i not in hits])
    gallery(idxs, loc, pt, f"gallery_{a.method}_{a.set}")
    print(f"gallery -> results/gallery_{a.method}_{a.set}.jpg  (green box = hit, red = miss, magenta dot = hand-marked pipe)")
    if a.target is not None:
        print("RESULT", "PASS" if rate >= a.target else "FAIL", f"(target {a.target})")
        sys.exit(0 if rate >= a.target else 1)


def cmd_confidence(a):
    from locate import CONF_TH
    loc, pt, ph = read_locate(a.method), points(), photos()
    idxs = [i for i in sorted(loc) if a.set == "all" or ph[i][1] == SETS[a.set]]
    conf = [i for i in idxs if float(loc[i]["score"]) >= CONF_TH]
    good = [i for i in conf if is_hit(loc[i], pt[i])]
    prec = len(good) / len(conf) if conf else 0.0
    print(f"method={a.method} set={a.set} threshold={CONF_TH}: {len(conf)}/{len(idxs)} marked confident, "
          f"{len(good)} of them hits -> precision {prec:.3f}")
    print("confident but wrong:", [i for i in conf if i not in good])
    print("flagged low-confidence:", [i for i in idxs if i not in conf])
    print("RESULT", "PASS" if prec >= 0.9 else "FAIL", "(target: >= 0.90 of confident finds are hits)")
    sys.exit(0 if prec >= 0.9 else 1)


def cmd_visits(a):
    """P5.1.3 two-shot vote: per visit (checkpoint + day) keep the shot with the higher confidence score."""
    from locate import visits
    pt, ph, vis = points(), photos(), visits()
    groups = {}
    for i, k in vis.items():
        groups.setdefault(k, []).append(i)
    hard_visits = {k for k, g in groups.items() if any(ph[i][1] == "3_hard" for i in g)}
    print(f"{len(groups)} visits ({len(hard_visits)} containing a hard photo)")
    for m in a.methods.split(","):
        loc = read_locate(m)
        res = {}
        for k, g in groups.items():
            pick = max(g, key=lambda i: float(loc[i]["score"] or 0))
            res[k] = (is_hit(loc[pick], pt[pick]), any(is_hit(loc[i], pt[i]) for i in g))
        def rate(keys):
            return sum(res[k][0] for k in keys) / len(keys)
        single = sum(is_hit(loc[i], pt[i]) for i in loc) / len(loc)
        print(f"method={m:8s} single-shot {single:.3f} | visit vote: all {rate(groups):.3f}, "
              f"hard visits {rate(hard_visits):.3f} | best possible (any shot hit) {sum(r[1] for r in res.values()) / len(res):.3f}")
        dis = [f"{k[0].split('CKP')[-1].strip()} {k[1]}" for k, g in groups.items() if len(g) > 1 and len({is_hit(loc[i], pt[i]) for i in g}) > 1]
        print(f"   visits whose shots disagree (one found, one not): {len(dis)} -> {dis}")


def cmd_rings(a):
    """P3: auto ring reading vs manual counts on the clear photos."""
    man = {int(r["idx"]): r for r in csv.DictReader(open(ROOT / "sorted/visibility_labels.csv", encoding="utf-8")) if r["rings_visible"] != ""}
    auto = {int(r["idx"]): r for r in csv.DictReader(open(ROOT / f"results/rings_{a.method}.csv"))}
    if a.pairs:
        from locate import visits
        vis, groups = visits(), {}
        for i, k in vis.items():
            groups.setdefault(k, []).append(i)
        both = [g for g in groups.values() if len(g) > 1 and all(auto[i]["rings"] != "" for i in g)]
        agree = [g for g in both if max(int(auto[i]["rings"]) for i in g) - min(int(auto[i]["rings"]) for i in g) <= 3]
        print(f"method={a.method}: visits with both shots read {len(both)}; two shots within 3 rings: {len(agree)} ({len(agree) / len(both):.3f})")
        print("visits differing by more than 3 rings:", [[(i, auto[i]["rings"]) for i in g] for g in both if g not in agree])
        print("RESULT PASS (agreement rate printed, disagreements listed)")
        return
    if a.dry:
        want = [62, 63, 75, 76, 86, 87]
        got = {i: auto[i]["state"] for i in want}
        print("dry gauges (manual 0 rings):", got)
        ok = all(v == "dry" for v in got.values())
        print("RESULT", "PASS" if ok else "FAIL", "(all six must be 'dry')")
        sys.exit(0 if ok else 1)
    tol = {"exact": 1, "est": 3}[a.conf]
    ids = [i for i in sorted(man) if man[i]["count_conf"] == a.conf]
    ok = [i for i in ids if auto[i]["rings"] != "" and abs(int(auto[i]["rings"]) - int(man[i]["rings_visible"])) <= tol]
    rate = len(ok) / len(ids)
    print(f"method={a.method} conf={a.conf}: |auto - manual| <= {tol} on {len(ok)}/{len(ids)} = {rate:.3f}")
    for i in ids:
        print(f"  {i:3d} manual {man[i]['rings_visible']:>2s}  auto {auto[i]['rings'] or '-':>2s} ({auto[i]['state']})" + ("" if i in ok else "   <- off"))
    print("RESULT", "PASS" if rate >= 0.8 else "FAIL", "(target 0.80)")
    sys.exit(0 if rate >= 0.8 else 1)


def ruler(img, box):
    """P5.2.1 exposed stem length in stem widths: no rings needed, self-scaled for drone distance/zoom."""
    x0, y0, x1, y1 = box
    crop = img[max(y0, 0):y1, max(x0, 0):x1]
    h, s, v = cv2.split(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV))
    stem = (((h < 12) | (h > 150)) & (s > 45) & (v > 35)) | ((h >= 92) & (h <= 128) & (s <= 135) & (v >= 55)) | ((s < 35) & (v > 120))
    W = stem.shape[1]
    centre = stem[:, int(W * 0.35):int(W * 0.65)].mean(axis=1)
    rows = np.nonzero(centre > 0.5)[0]
    if len(rows) < 10:
        return None
    widths = stem[rows].sum(axis=1)
    return (rows[-1] - rows[0]) / max(float(np.median(widths)), 1.0)


def spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def cmd_ruler(a):
    man = {int(r["idx"]): int(r["rings_visible"]) for r in csv.DictReader(open(ROOT / "sorted/visibility_labels.csv", encoding="utf-8")) if r["rings_visible"] != ""}
    loc, ph = read_locate(a.method), photos()
    pairs = []
    for i in sorted(man):
        r = loc[i]
        if not r["x0"]:
            continue
        img = cv2.imdecode(np.fromfile(str(ph[i][0]), np.uint8), cv2.IMREAD_COLOR)
        q = ruler(img, [int(r[k]) for k in ("x0", "y0", "x1", "y1")])
        if q is not None:
            pairs.append((i, man[i], q))
    rho = spearman([p[1] for p in pairs], [p[2] for p in pairs])
    for i, m, q in pairs:
        print(f"  {i:3d} manual rings {m:2d}   stem length / width {q:5.1f}")
    print(f"method={a.method}: {len(pairs)} clear photos measured; Spearman rho = {rho:.3f}")
    print("RESULT", "PASS" if rho >= 0.8 else "FAIL", "(target >= 0.8)")
    sys.exit(0 if rho >= 0.8 else 1)


def main():
    ap = argparse.ArgumentParser()
    s = ap.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("locate")
    x.add_argument("--set", default="all", choices=["clear", "partial", "hard", "all"])
    x.add_argument("--method", default="colour")
    x.add_argument("--target", type=float)
    x = s.add_parser("confidence")
    x.add_argument("--set", default="all", choices=["clear", "partial", "hard", "all"])
    x.add_argument("--method", default="colour")
    x = s.add_parser("rings")
    x.add_argument("--method", default="colour")
    x.add_argument("--conf", default="exact", choices=["exact", "est"])
    x.add_argument("--pairs", action="store_true")
    x.add_argument("--dry", action="store_true")
    x = s.add_parser("ruler")
    x.add_argument("--method", default="colour")
    x = s.add_parser("visits")
    x.add_argument("--methods", default="colour,cascade")
    a = ap.parse_args()
    {"locate": cmd_locate, "confidence": cmd_confidence, "visits": cmd_visits, "rings": cmd_rings, "ruler": cmd_ruler}[a.cmd](a)


if __name__ == "__main__":
    main()
