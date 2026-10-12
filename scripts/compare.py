"""Every photo through every method, scored the same way -> docs/comparison.md, data/v{1,2}_reads.csv,
models/v{1,2}_confidence.json.

Methods
  v0        the company's detector, rebuilt from its description (gauge/v0.py, data/v0_reads.csv)
  colour    our colour method: colour isolation + gauge memory + shot transfer, method 3 final + rings.py
            (carbonmint-testing@7d32b19, vendored in methods/teammate; results in methods/teammate/results)
  reader    our P0-P6 reader with its own confidence score (data/photo_reads.csv: v1 reader output, frozen at 53c006c)
  v1        our reader + trained confidence model (leave-one-plot-out) + bad-gauge check + company accept rule
  v2        v1 + pitch and gap-count fixes (data/photo_reads_v2.csv, python -m gauge.run) + colour-method locator fallback

Company metric (the target): share of correct-gauge photos that are ACCEPTED (confidence >= 0.7) AND EXACT.
Labels: data/labels.csv (Claude-read, human spot-checked in two rounds)."""
import csv, json, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
sys.path.insert(0, ".")
from gauge import v1

lab = {r["photo"]: r for r in csv.DictReader(open("data/labels.csv", newline=""))}
reads = list(csv.DictReader(open("data/photo_reads.csv", newline="")))
photos = [r["photo"] for r in reads]
truth = {p: float(lab[p]["rings"]) for p in photos}
visit_of = {p: lab[p]["visit"] for p in photos}
plot_of = {p: lab[p]["plot"] for p in photos}


def num(v):
    return None if v in ("", None, "None") else float(v)


# --- v0 -------------------------------------------------------------------------------------------
v0 = {r["photo"]: dict(cm=num(r["cm"]), conf=float(r["confidence"]), acc=r["accepted"] == "True")
      for r in csv.DictReader(open("data/v0_reads.csv", newline=""))}

# --- colour method ---------------------------------------------------------------------------------------
T = Path("methods/teammate")
key = {int(r["idx"]): f'{r["checkpoint_folder"]}/{r["file"]}' for r in
       csv.DictReader(open(T / "sorted/visibility_labels.csv", encoding="utf-8"))}
loc = {int(r["idx"]): r for r in csv.DictReader(open(T / "results/locate_method3final.csv"))}
tm = {}
for r in csv.DictReader(open(T / "results/rings_method3final.csv")):
    i = int(r["idx"])
    cm = None if r["state"] == "unreadable" else float(r["rings"] or 0)
    sure = loc[i]["state"] in ("colour", "found-visible")          # their own "confident" states (score >= 0.30)
    tm[key[i]] = dict(cm=cm, conf=float(loc[i]["score"] or 0), acc=sure and cm is not None)

# --- our reader, its own confidence -------------------------------------------------------------------
rd = {r["photo"]: dict(cm=num(r["rings"]), conf=float(r["confidence"] or 0)) for r in reads}
for d in rd.values():
    d["acc"] = d["cm"] is not None and d["conf"] >= 0.7

# --- v1 / v2: trained confidence, leave-one-plot-out --------------------------------------------------
def trained(reads, name):
    """LOPO probabilities for every photo, the full model saved to models/<name>_confidence.json, and
    data/<name>_reads.csv. Returns {photo: dict(cm, conf, acc, note)}."""
    by_visit = defaultdict(list)
    for r in reads:
        by_visit[r["visit"]].append(r)
    X = np.array([v1.features(r, [s["rings"] for s in by_visit[r["visit"]] if s is not r]) for r in reads])
    y = np.array([float(r["rings"] != "" and float(r["rings"]) == truth[r["photo"]]) for r in reads])
    prob = np.zeros(len(reads))
    for plot in sorted(set(plot_of.values())):
        te = np.array([plot_of[r["photo"]] == plot for r in reads])
        prob[te] = v1.Model().fit(X[~te], y[~te]).prob(X[te])
    Path("models").mkdir(exist_ok=True)
    Path(f"models/{name}_confidence.json").write_text(v1.Model().fit(X, y).to_json())
    out = {}
    for r, p in zip(reads, prob):
        d = v1.decide(r, p)
        out[r["photo"]] = dict(cm=d["cm"], conf=d["confidence"], acc=d["accepted"], note=d["note"] or r.get("source", ""))
    with open(f"data/{name}_reads.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["photo", "plot", "visit", "cm", "confidence_lopo", "accepted", "note", "label"])
        for p in photos:
            d = out[p]
            w.writerow([p, plot_of[p], visit_of[p], d["cm"], d["conf"], int(d["acc"]), d["note"], truth[p]])
    return out


v1r = trained(reads, "v1")
# v2: reader fixes (shortest strong pitch lag, gap-by-gap count) + the colour method's locator when the reader finds no rod
tmraw = {key[int(r["idx"])]: r for r in csv.DictReader(open(T / "results/rings_method3final.csv")) if int(r["idx"]) in key}
reads2 = {r["photo"]: r for r in csv.DictReader(open("data/photo_reads_v2.csv", newline=""))}
v2r = trained([v1.fallback(reads2[p], tmraw[p]) for p in photos], "v2")

# --- scoring ----------------------------------------------------------------------------------------
METHODS = [("v0 (company, rebuilt)", v0), ("Colour method", tm), ("Our reader, own score", rd), ("v1", v1r),
           ("**v2**", v2r)]


def score(m):
    n = len(photos)
    ex = lambda p: m[p]["cm"] is not None and m[p]["cm"] == truth[p]
    n1 = lambda p: m[p]["cm"] is not None and abs(m[p]["cm"] - truth[p]) <= 1
    acc = [p for p in photos if m[p]["acc"]]
    vis = defaultdict(list)
    for p in photos:
        vis[visit_of[p]].append(p)
    vok = 0
    for v, ps in vis.items():
        a = [m[p]["cm"] for p in ps if m[p]["acc"]]
        labs = sorted(truth[p] for p in ps)
        t = labs[len(labs) // 2] if len(labs) % 2 else sum(labs) / len(labs)
        vok += bool(a) and abs(sum(a) / len(a) - t) < 0.5
    return dict(n=n, acc=len(acc), acc_exact=sum(map(ex, acc)), prec=sum(map(ex, acc)) / len(acc) if acc else 0,
                exact=sum(map(ex, photos)), pm1=sum(map(n1, photos)), none=sum(m[p]["cm"] is None for p in photos),
                visits=len(vis), visit_ok=vok)


pct = lambda a, b: f"{100 * a / b:.1f}%"
res = {name: score(m) for name, m in METHODS}
L = ["# v0 vs v1 vs v2: every photo through every method", "",
     "Generated by `python scripts/compare.py`. 127 drone photos (7 plots, 66 visits, 23 Sep to 6 Oct 2026); labels are "
     "Claude-read ring counts, human spot-checked (round 1: 10/15 exact, labels fixed; round 2: 15/15). All photos show "
     "a correct gauge.", "",
     "**Company metric** (the target is 70-80%): a photo counts only when it is accepted (confidence >= 0.7) **and** its "
     "reading is exact (1 ring = 1 cm).", "",
     "| Method | Accepted & exact (company metric) | Accepted | Right when accepted | Exact, all photos | Within 1, all photos | No reading | Visits accepted & exact |",
     "|---|---|---|---|---|---|---|---|"]
for name, s in res.items():
    L.append(f"| {name} | **{s['acc_exact']}/{s['n']} = {pct(s['acc_exact'], s['n'])}** | {pct(s['acc'], s['n'])} | "
             f"{pct(s['acc_exact'], max(s['acc'], 1))} | {pct(s['exact'], s['n'])} | {pct(s['pm1'], s['n'])} | {s['none']} | "
             f"{s['visit_ok']}/{s['visits']} = {pct(s['visit_ok'], s['visits'])} |")
L += ["", "Notes:",
      "- **v0** is rebuilt in Python from the company's written description of `src/enhanced-detector.ts`; numbers the "
      "description leaves open are marked ASSUMED in `gauge/v0.py`. Its ~50% comes from the company's own photos; on these "
      "photos it scores lower. Diagnostic (`scripts/v0_diag.py`): its colour rule needs value >= 50%, but shaded rings here "
      "sit at about 25-40%; relaxing only that rule lifts it from 19 to 55 accepted-and-exact. The magenta hue rule "
      "(140-175) changes nothing on these photos.",
      "- **Colour method** has no confidence on its ring count; 'accepted' = its locator's own confident states "
      "(score >= 0.30), not the company's 0.7.",
      "- **Our reader, own score**: same readings as v1, but its untrained confidence rarely reaches 0.7.",
      "- **v1** confidence is a logistic model trained **leave-one-plot-out**: each plot's photos are scored by a model "
      "that never saw that plot. Accept = probability >= 0.7. Bad-gauge check: "
      f"{sum(1 for d in v1r.values() if d['note'].startswith('bad gauge'))} of 127 correct-gauge photos falsely flagged.",
      "- **v2** = v1 plus two reader fixes and the colour method's locator: (1) the ring gap is the shortest autocorrelation lag "
      "at least 0.75 as strong as the best (the best can be 2-4x the true gap); (2) rings are counted gap by gap against "
      "the local gap, since perspective changes the gap along the rod; (3) when our rod finder sees nothing, the "
      "colour method's locator is used (local lane only: needs OpenCV). Same features, same leave-one-plot-out training. "
      "Tried and dropped (no gain or more errors on these photos): Lanczos 2-3x upscaling of small rods, an extra ring at "
      "the sleeve, extending the count along a faint rhythm, extra confidence signals, and the colour method's count / box / "
      "score as confidence signals.", ""]
# per held-out plot for v1
L += ["## v2 per held-out plot", "", "| Plot | Photos | Accepted & exact | Accepted | Right when accepted |", "|---|---|---|---|---|"]
for plot in sorted(set(plot_of.values())):
    ps = [p for p in photos if plot_of[p] == plot]
    a = [p for p in ps if v2r[p]["acc"]]
    ae = sum(v2r[p]["cm"] == truth[p] for p in a)
    L.append(f"| {plot} | {len(ps)} | {ae}/{len(ps)} = {pct(ae, len(ps))} | {len(a)} | {pct(ae, max(len(a), 1))} |")
# wrong but accepted (the costly error)
bad = [p for p in photos if v2r[p]["acc"] and v2r[p]["cm"] != truth[p]]
L += ["", f"## v2 accepted but not exact ({len(bad)})", "", "| Photo | Read | Label | Confidence |", "|---|---|---|---|"]
L += [f"| `{p.split('/')[-1]}` | {v2r[p]['cm']} | {truth[p]} | {v2r[p]['conf']} |" for p in bad]
Path("docs/comparison.md").write_text("\n".join(L) + "\n", encoding="utf8")
print("\n".join(l for l in L if "/127 = " in l and l.startswith("| ")))
json.dump({k: v for k, v in res.items()}, open("data/comparison.json", "w"), indent=1)
