"""Pre-registered Upscayl test (docs/upscale_check.md).
  python scripts/upscale_eval.py upscale     # make every crop and upscale it (cached; slow, run once)
  python scripts/upscale_eval.py score       # baseline, Test A, Test B, S1, S2 -> data/upscale_eval.json + tables
Scoring is the same as scripts/compare.py: exact count, all photos, confidence trained leave one field out."""
import csv, json, sys, time
from collections import defaultdict
from pathlib import Path
import numpy as np
from PIL import Image
sys.path[:0] = [".", "service"]
from gauge import v1, upscale as U
from gauge.detect import detect, ring_mask
from gauge.measure import read

T = Path("methods/teammate")
key = {int(r["idx"]): f'{r["checkpoint_folder"]}/{r["file"]}' for r in csv.DictReader(open(T / "sorted/visibility_labels.csv", encoding="utf-8"))}
# the team's recounted key (carbonmint-testing, 12 Oct) for the looser +-1/+-3 rule, as in the 79.7% note
team = {key[int(r["idx"])]: r for r in csv.DictReader(open("data/team_key_recounted.csv", encoding="utf-8")) if int(r["idx"]) in key}
tmraw = {key[int(r["idx"])]: r for r in csv.DictReader(open(T / "results/rings_method3final.csv")) if int(r["idx"]) in key}
lab = {r["photo"]: r for r in csv.DictReader(open("data/labels.csv"))}
reads = [v1.fallback(r, tmraw[r["photo"]]) for r in csv.DictReader(open("data/photo_reads_v2.csv", newline=""))]
photos = [r["photo"] for r in reads]
truth = {p: float(lab[p]["rings"]) for p in photos}
plot = {p: lab[p]["plot"] for p in photos}
CROPS = Path("data/cache/upscayl_crops.json")
num = lambda v: None if v in ("", None, "None") else float(v)


def load(p):
    return np.asarray(Image.open("way points/" + p).convert("RGB"))


def crop_box(r, im):
    if r.get("cx") not in ("", None):
        return U.crop_for_rod(r, im.shape)
    from gaugesvc.engine import colour_locate        # no rod: our colour method's locator box
    _, box = colour_locate(open("way points/" + r["photo"], "rb").read())
    return None if box is None else U.crop_for_box(box, im.shape)


def cmd_upscale():
    """Every photo's gauge crop, its stripe-free cap (S1) and its shrunk crop (S2), upscaled once and cached."""
    boxes = {}
    jobs = []                                            # (name, array)
    for r in reads:
        im = load(r["photo"])
        b = crop_box(r, im)
        boxes[r["photo"]] = b
        if b:
            x0, y0, x1, y1 = b
            jobs.append(("rod", r["photo"], im[y0:y1, x0:x1].copy()))
    CROPS.parent.mkdir(parents=True, exist_ok=True)
    CROPS.write_text(json.dumps(boxes))
    # pre-registered order: Test A's triggered crops first, then the rest
    trig = {r["photo"] for r in reads if U.triggers(r) or r.get("source")}
    jobs.sort(key=lambda j: j[1] not in trig)
    t0 = time.time()
    for i in range(0, len(jobs), 4):
        chunk = jobs[i:i + 4]
        U.upscale_many([j[2] for j in chunk])
        print(f"{min(i + 4, len(jobs))}/{len(jobs)} crops upscaled, {time.time() - t0:.0f} s", flush=True)
    for name, arrs in (("caps", cap_crops()), ("shrunk", [s for _, s, _ in shrunk_crops()])):
        for i in range(0, len(arrs), 8):
            U.upscale_many(arrs[i:i + 8])
        print(f"{name}: {len(arrs)} crops upscaled, {time.time() - t0:.0f} s", flush=True)


def cap_crops():
    """S1b: the plain grey cap above the first stripe of accepted-and-exact photos (cap >= 1.5 stripe gaps)."""
    v2 = {r["photo"]: r for r in csv.DictReader(open("data/v2_reads.csv"))}
    out = []
    for r in reads:
        p = r["photo"]
        if not (v2[p]["accepted"] == "1" and num(v2[p]["cm"]) == truth[p]):
            continue
        if num(r.get("top_y")) is None or num(r.get("pitch_px")) is None:
            continue
        top, first, pitch = num(r["top_y"]), num(r["first_y"]), num(r["pitch_px"])
        y0, y1 = int(top), int(first - 0.6 * pitch)
        if y1 - y0 < 1.5 * pitch - 0.6 * pitch:
            continue
        cx, h = num(r["cx"]), num(r["half"])
        im = load(p)
        c = im[max(0, y0):y1, int(cx - 2 * h):int(cx + 2 * h)].copy()
        if c.shape[0] >= 8 and c.shape[1] >= 8:
            out.append(c)
    return out


def shrunk_crops():
    """S2: accepted-and-exact photos with half-width >= 25 px; crop shrunk to a quarter (area average)."""
    v2 = {r["photo"]: r for r in csv.DictReader(open("data/v2_reads.csv"))}
    boxes = json.loads(CROPS.read_text())
    out = []
    for r in reads:
        p = r["photo"]
        if v2[p]["accepted"] == "1" and num(v2[p]["cm"]) == truth[p] and (num(r.get("half")) or 0) >= 25 and boxes.get(p):
            x0, y0, x1, y1 = boxes[p]
            c = Image.fromarray(load(p)[y0:y1, x0:x1])
            s = c.resize((max(8, c.width // 4), max(8, c.height // 4)), Image.BOX)
            out.append((p, np.asarray(s).copy(), c.size))
    return out


def stripes_in(img):
    """Stripe-like bands in a crop: runs of rows where ring paint covers > 15% of the row."""
    on = ring_mask(img.astype(np.int16)).mean(1) > 0.15
    runs, n = 0, 0
    for v in on:
        n = n + 1 if v else 0
        runs += n == 3                                   # count each run once it is 3 rows tall
    return runs


def variant(mode, boxes):
    """Rows for Test A (mode 'A') or Test B (mode 'B'), plus one log line per touched photo."""
    byv = defaultdict(list)
    for r in reads:
        byv[r["visit"]].append(r)
    todo = [r for r in reads if boxes.get(r["photo"]) and (mode == "B" or U.triggers(r) or r.get("source"))]
    ups = {}
    for r in todo:
        x0, y0, x1, y1 = boxes[r["photo"]]
        up = U.upscale_many([load(r["photo"])[y0:y1, x0:x1].copy()])[0]   # from the cache
        ups[r["photo"]] = None if up is None else U.read_upscaled(up, x0, y0)
    rows, log = [], []
    for r in reads:
        p = r["photo"]
        if p not in ups:
            rows.append(dict(r, upscaled=0)); continue
        twin = next((s["rings"] for s in byv[r["visit"]] if s is not r and s.get("rings") not in ("", None)), None)
        ok, why = U.adopt(r["rings"], ups[p], twin)
        new = dict(r, **{k: v for k, v in ups[p].items()}, upscaled=1, source="") if ok else dict(r, upscaled=0)
        trig = ", ".join(U.triggers(r)) or ("no rod (colour locator)" if r.get("source") else "all photos")
        log.append(dict(photo=p, trigger=trig, before=num(r["rings"]), upscaled=num(ups[p]["rings"]) if ups[p] else None,
                        after=num(new["rings"]), truth=truth[p], twin=num(twin), decision=why))
        rows.append(new)
    return rows, log


def lopo(rows, extra):
    byv = defaultdict(list)
    for r in rows:
        byv[r["visit"]].append(r)
    feat = lambda r: np.r_[v1.features(r, [s["rings"] for s in byv[r["visit"]] if s is not r]), [float(r.get("upscaled", 0))] if extra else []]
    X = np.array([feat(r) for r in rows])
    y = np.array([float(r["rings"] not in ("", None) and float(r["rings"]) == truth[r["photo"]]) for r in rows])
    prob = np.zeros(len(rows))
    pl = np.array([plot[r["photo"]] for r in rows])
    for q in sorted(set(pl)):
        te = pl == q
        prob[te] = v1.Model().fit(X[~te], y[~te]).prob(X[te])
    return {r["photo"]: v1.decide(r, p) for r, p in zip(rows, prob)}


def score(dec):
    acc = [p for p in photos if dec[p]["accepted"]]
    ok = [p for p in acc if dec[p]["cm"] == truth[p]]
    cnt = [p for p in photos if team[p]["count_conf"] != "uncountable"]
    tol = lambda p: 1 if team[p]["count_conf"] == "exact" else 3
    loose = [p for p in cnt if dec[p]["accepted"] and dec[p]["cm"] is not None and abs(dec[p]["cm"] - float(team[p]["rings_visible"])) <= tol(p)]
    return dict(accepted_exact=len(ok), pct=round(100 * len(ok) / len(photos), 1), accepted=len(acc), wrong=len(acc) - len(ok),
                review=sum(1 for p in photos if dec[p]["cm"] is not None and not dec[p]["accepted"]),
                no_gauge=sum(1 for p in photos if dec[p]["cm"] is None), loose=f"{len(loose)}/{len(cnt)}")


def cmd_score():
    boxes = json.loads(CROPS.read_text())
    out = {"baseline": score(lopo([dict(r, upscaled=0) for r in reads], False))}
    for m in ("A", "B"):
        rows, log = variant(m, boxes)
        dec = lopo(rows, True)
        base = lopo([dict(r, upscaled=0) for r in reads], False)
        for e in log:
            e.update(accepted_before=base[e["photo"]]["accepted"], accepted_after=dec[e["photo"]]["accepted"])
        out[m] = dict(score(dec), touched=len(log), adopted=sum(e["decision"].startswith("adopted") for e in log),
                      changed=sum(e["after"] != e["before"] for e in log), log=log)
    # S1: dry gauges and stripe-free caps must gain no stripes
    dry = [e for e in out["B"]["log"] if e["truth"] == 0]
    out["S1_dry"] = dict(photos=len(dry), invented=[e["photo"] for e in dry if (e["upscaled"] or 0) > 0])
    caps = cap_crops()
    upc = U.upscale_many(caps)
    out["S1_caps"] = dict(crops=len(caps), engine_ok=sum(u is not None for u in upc),
                          with_stripes=sum(1 for u in upc if u is not None and stripes_in(u) > 0),
                          with_stripes_before=sum(1 for c in caps if stripes_in(np.asarray(Image.fromarray(c).resize((c.shape[1] * 4, c.shape[0] * 4), Image.LANCZOS))) > 0))
    # S2: shrink to a quarter, restore x4 with Upscayl and with Lanczos, read
    res = defaultdict(int); n = 0
    for p, s, size in shrunk_crops():
        n += 1
        restored = {"upscayl": U.upscale_many([s])[0], "lanczos": np.asarray(Image.fromarray(s).resize((s.shape[1] * 4, s.shape[0] * 4), Image.LANCZOS))}
        for k, im in restored.items():
            if im is None:
                continue
            d = detect(im.astype(np.int16))
            res[k] += d is not None and read(im.astype(np.int16), d)["rings"] == truth[p]
    out["S2"] = dict(photos=n, **{f"exact_{k}": v for k, v in res.items()})
    Path("data/upscale_eval.json").write_text(json.dumps(out, indent=1))
    for k in ("baseline", "A", "B"):
        print(k, {x: y for x, y in out[k].items() if x != "log"})
    print("S1", out["S1_dry"], out["S1_caps"]); print("S2", out["S2"])


if __name__ == "__main__":
    {"upscale": cmd_upscale, "score": cmd_score}[sys.argv[1]]()
