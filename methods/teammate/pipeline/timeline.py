"""P4.1.1 daily water-level timeline per checkpoint + P5.2.2 water-physics flags.

One reading per visit: the shot with the higher locate confidence (two-shot vote).
cm = rings * CM_PER_RING (working assumption, docs/decisions.md).
Flags (water physics of an AWD field):
  drop_too_fast  level fell more than MAX_DROP_CM per day: fields drain slowly, so this is likely a misread
  shots_disagree the two shots of the visit differ by more than 3 rings
  rise           level rose: allowed (irrigation or rain), labelled so it can be checked against irrigation logs

python pipeline/timeline.py [--method colour|cascade]  -> results/timeline_<method>.csv
"""
import csv, datetime, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from isolate import ROOT
from locate import visits

CM_PER_RING = 1.0   # ponytail: assumption until CarbonMint confirms (P0.1.4); one value, change here
MAX_DROP_CM = 5.0   # per day; AWD fields typically lose ~1-2 cm/day, 5 leaves room for hot, windy days


def build(method):
    loc = {int(r["idx"]): r for r in csv.DictReader(open(ROOT / f"results/locate_{method}.csv"))}
    rg = {int(r["idx"]): r for r in csv.DictReader(open(ROOT / f"results/rings_{method}.csv"))}
    groups = {}
    for i, k in visits().items():
        groups.setdefault(k, []).append(i)
    rows = []
    for (cp, day), g in groups.items():
        pick = max(g, key=lambda i: float(loc[i]["score"] or 0))
        r = rg[pick]
        read = [int(rg[i]["rings"]) for i in g if rg[i]["rings"] != ""]
        rows.append({"checkpoint": cp.split("CKP")[-1].strip(" -") or cp, "date": datetime.datetime.strptime(day, "%d%m%y").date(),
                     "photo": pick, "state": r["state"], "rings": r["rings"],
                     "cm": "" if r["rings"] == "" else round(int(r["rings"]) * CM_PER_RING, 1),
                     "flag": "shots_disagree" if len(read) > 1 and max(read) - min(read) > 3 else ""})
    rows.sort(key=lambda r: (r["checkpoint"], r["date"]))
    prev = {}
    for r in rows:
        p = prev.get(r["checkpoint"])
        if p and r["cm"] != "" and p["cm"] != "":
            days = max((r["date"] - p["date"]).days, 1)
            if (p["cm"] - r["cm"]) / days > MAX_DROP_CM:
                r["flag"] = ";".join(filter(None, [r["flag"], f"drop_too_fast({p['cm']}->{r['cm']} cm in {days} d)"]))
            elif r["cm"] > p["cm"] + 3:
                r["flag"] = ";".join(filter(None, [r["flag"], f"rise({p['cm']}->{r['cm']} cm)"]))
        if r["cm"] != "":
            prev[r["checkpoint"]] = r
    out = ROOT / f"results/timeline_{method}.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return rows, out


if __name__ == "__main__":
    m = sys.argv[sys.argv.index("--method") + 1] if "--method" in sys.argv else "colour"
    rows, out = build(m)
    cur = None
    for r in rows:
        if r["checkpoint"] != cur:
            cur = r["checkpoint"]; print(f"\n{cur}")
        print(f"  {r['date']}  photo {r['photo']:3d}  {r['state']:10s} rings {str(r['rings']):>2s}  cm {str(r['cm']):>4s}  {r['flag']}")
    flagged = [r for r in rows if "drop_too_fast" in r["flag"] or "shots_disagree" in r["flag"]]
    print(f"\n{len(rows)} visits -> {out.relative_to(ROOT)}; flagged for review: {len(flagged)}")
    ok = len(rows) == 66 and all(k in rows[0] for k in ("checkpoint", "date", "rings", "cm", "state", "flag"))
    print("RESULT", "PASS" if ok else "FAIL")
