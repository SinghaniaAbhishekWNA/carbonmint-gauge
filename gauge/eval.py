"""P5 Evaluation against the silver labels (data/labels.csv).
  python -m gauge.eval --mode baseline   plain ring counter
  python -m gauge.eval --mode full       measure + fusion + timeline + review rule, leave-one-plot-out
Accuracy = share within 0 (exact, half-ring tolerance) or 1 ring of the label, per photo and per visit.
Writes / updates docs/results.md."""
import argparse, csv, re
from collections import defaultdict
from pathlib import Path
from .fuse import fuse, timeline, accept, smooth

RESULTS = Path("docs/results.md")
TAUS = [0.0, 0.2, 0.3, 0.4, 0.5, 0.6]


def num(v):
    return None if v in ("", None) else float(v)


def load():
    lab = {r["photo"]: r for r in csv.DictReader(open("data/labels.csv"))}
    reads = list(csv.DictReader(open("data/photo_reads.csv")))
    for r in reads:
        r["label"] = float(lab[r["photo"]]["rings"])
        r["label_conf"] = lab[r["photo"]]["confidence"]
    return reads


def hit(pred, truth, tol):
    return pred is not None and abs(pred - truth) <= tol + 1e-9


def score(pairs):
    n = len(pairs)
    return dict(n=n, exact=sum(hit(p, t, 0.5 - 1e-6) for p, t in pairs) / n if n else 0,
                pm1=sum(hit(p, t, 1) for p, t in pairs) / n if n else 0)


def visits(reads, key):
    by = defaultdict(list)
    for r in reads:
        by[r["visit"]].append(r)
    out = []
    for v, rs in by.items():
        f = fuse([dict(rings=num(r[key]), confidence=float(r["confidence"] or 0)) for r in rs])
        labs = sorted(r["label"] for r in rs)
        out.append(dict(visit=v, plot=rs[0]["plot"], date=rs[0]["date"], label=labs[len(labs) // 2] if len(labs) % 2
                        else sum(labs) / len(labs), photos=[r["photo"] for r in rs], **f))
    # timeline spike check per plot
    for plot in {o["plot"] for o in out}:
        seq = sorted((o for o in out if o["plot"] == plot), key=lambda o: o["date"])
        for o, fl in zip(seq, timeline([o["rings"] for o in seq])):
            if fl:
                o["flags"] = o["flags"] + ["timeline spike"]
    return sorted(out, key=lambda o: (o["plot"], o["date"]))


def pick_tau(vs):
    """Smallest threshold whose auto-accepted visits are >= 90% within 1 ring (on the training plots only)."""
    for tau in TAUS:
        acc = [o for o in vs if accept(o["confidence"], o["flags"], tau)]
        if acc and score([(o["rings"], o["label"]) for o in acc])["pm1"] >= 0.9:
            return tau
    return TAUS[-1]


def full(reads):
    vs = visits(reads, "rings")
    plots = sorted({o["plot"] for o in vs})
    folds = []
    for p in plots:
        tau = pick_tau([o for o in vs if o["plot"] != p])
        held = [o for o in vs if o["plot"] == p]
        for o in held:
            o["tau"], o["auto"] = tau, accept(o["confidence"], o["flags"], tau)
        auto = [o for o in held if o["auto"]]
        folds.append(dict(plot=p, tau=tau, visits=len(held), **score([(o["rings"], o["label"]) for o in held]),
                          auto=len(auto), auto_pm1=score([(o["rings"], o["label"]) for o in auto])["pm1"] if auto else None))
    return vs, folds


def pct(x):
    return "-" if x is None else f"{100 * x:.1f}%"


def write_section(name, body):
    text = RESULTS.read_text(encoding="utf8") if RESULTS.exists() else "# Results\n\n"
    pat = re.compile(rf"<!-- {name} -->.*?<!-- /{name} -->", re.S)
    block = f"<!-- {name} -->\n{body.strip()}\n<!-- /{name} -->"
    text = pat.sub(block, text) if pat.search(text) else text.rstrip() + "\n\n" + block + "\n"
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(text, encoding="utf8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["baseline", "full"], required=True)
    a = ap.parse_args()
    reads = load()
    key = "naive" if a.mode == "baseline" else "rings"
    ph = score([(num(r[key]), r["label"]) for r in reads])
    if a.mode == "baseline":
        vs = visits(reads, "naive")
        vi = score([(o["rings"], o["label"]) for o in vs])
        body = (f"## Baseline: plain ring counter\n\nCounts ring bands that cover at least 70% of the rod width "
                f"(what a quick counting script does). Same photos, same silver labels.\n\n"
                f"| Level | n | Exact | Within 1 ring |\n|---|---|---|---|\n"
                f"| Photo | {ph['n']} | {pct(ph['exact'])} | {pct(ph['pm1'])} |\n"
                f"| Visit (two shots fused) | {vi['n']} | {pct(vi['exact'])} | {pct(vi['pm1'])} |\n")
        write_section("baseline", body)
        print(body)
        return
    vs, folds = full(reads)
    vi = score([(o["rings"], o["label"]) for o in vs])
    auto = [o for o in vs if o["auto"]]
    au = score([(o["rings"], o["label"]) for o in auto])
    hi = [r for r in reads if r["label_conf"] == "high"]
    phh = score([(num(r["rings"]), r["label"]) for r in hi])
    lines = [f"## Full pipeline (measure, fuse, timeline, review rule), leave-one-plot-out\n",
             "Only the review threshold is fitted, on the six training plots of each fold. Labels are Claude-read and "
             "were checked by a person in two seeded rounds of 15 (round 1: 10/15 exact, so labels were fixed and "
             "switched to whole rings; round 2: 15/15). The reader's rules were written while looking at all seven "
             "plots, so a fresh batch of visits is still the real test.\n",
             "| Level | n | Exact | Within 1 ring |", "|---|---|---|---|",
             f"| Photo | {ph['n']} | {pct(ph['exact'])} | {pct(ph['pm1'])} |",
             f"| Photo, clear labels only | {phh['n']} | {pct(phh['exact'])} | {pct(phh['pm1'])} |",
             f"| Visit (all) | {vi['n']} | {pct(vi['exact'])} | {pct(vi['pm1'])} |",
             f"| Visit, auto-accepted | {au['n']} | {pct(au['exact'])} | {pct(au['pm1'])} |",
             f"\nReview share: {len(vs) - len(auto)}/{len(vs)} visits ({pct((len(vs) - len(auto)) / len(vs))}) go to a person.\n",
             "### Per held-out plot\n", "| Plot | Threshold | Visits | Exact | Within 1 | Auto-accepted | Auto within 1 |",
             "|---|---|---|---|---|---|---|"]
    lines += [f"| {f['plot']} | {f['tau']} | {f['visits']} | {pct(f['exact'])} | {pct(f['pm1'])} | {f['auto']} | {pct(f['auto_pm1'])} |"
              for f in folds]
    lines += ["\n### Misses (visit off by more than 1 ring)\n", "| Plot | Date | Label | Read | Confidence | Flags | Crops |",
              "|---|---|---|---|---|---|---|"]
    for o in vs:
        if not hit(o["rings"], o["label"], 1):
            crops = ", ".join(f"`data/crops/{Path(p).stem}.jpg`" for p in o["photos"])
            lines.append(f"| {o['plot']} | {o['date']} | {o['label']} | {o['rings']} | {o['confidence']} | "
                         f"{'; '.join(o['flags']) or '-'} | {crops} |")
    body = "\n".join(lines)
    write_section("full", body)
    with open("data/readings.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["plot", "date", "visit", "rings_raw", "rings_smoothed", "label", "confidence", "flags", "auto_accepted"])
        for plot in sorted({o["plot"] for o in vs}):
            seq = [o for o in vs if o["plot"] == plot]
            for o, sm in zip(seq, smooth([o["rings"] for o in seq])):
                w.writerow([o["plot"], o["date"], o["visit"], o["rings"], sm, o["label"], o["confidence"],
                            "; ".join(o["flags"]), int(o["auto"])])
    print(body)


if __name__ == "__main__":
    main()
