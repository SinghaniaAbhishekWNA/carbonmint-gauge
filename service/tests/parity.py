"""The service must give the research code's answers: python service/tests/parity.py <report.json>
Research path = data/photo_reads_v2.csv (python -m gauge.run) + the colour-method fallback + the full v1 model
(models/v2_confidence.json) + the company rule. Compares, per photo, the reading and the accept decision."""
import csv, json, sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from gauge import v1  # noqa: E402

rep = json.load(open(sys.argv[1], encoding="utf-8"))
svc = {p["file"].split("/", 1)[1] if p["file"].startswith("way points/") else p["file"]: p for p in rep["photos"]}
reads = list(csv.DictReader(open(REPO / "data/photo_reads_v2.csv", newline="")))
T = REPO / "methods/teammate"
key = {int(r["idx"]): f'{r["checkpoint_folder"]}/{r["file"]}' for r in csv.DictReader(open(T / "sorted/visibility_labels.csv", encoding="utf-8"))}
col = {key[int(r["idx"])]: r for r in csv.DictReader(open(T / "results/rings_method3final.csv")) if int(r["idx"]) in key}
lab = {r["photo"]: float(r["rings"]) for r in csv.DictReader(open(REPO / "data/labels.csv"))}
rows = [v1.fallback(r, col[r["photo"]]) for r in reads]
by_visit = defaultdict(list)
for r in rows:
    by_visit[r["visit"]].append(r)
m = v1.Model.from_json((REPO / "models/v2_confidence.json").read_text())
same_read = same_acc = 0
diffs = []
for r in rows:
    s = svc[r["photo"]]
    res_n = None if r["rings"] in ("", None) else float(r["rings"])
    svc_n = s.get("stripes") if s.get("stripes") is not None else s.get("candidate_stripes")
    if res_n is None:
        res_acc = False
    else:
        p = float(m.prob(v1.features(r, [x["rings"] for x in by_visit[r["visit"]] if x is not r])[None, :])[0])
        res_acc = v1.decide(r, p)["accepted"]
    ok_n = (res_n is None and svc_n is None) or (res_n is not None and svc_n is not None and int(res_n) == svc_n)
    ok_a = res_acc == (s["status"] == "accepted")
    same_read += ok_n; same_acc += ok_a
    if not (ok_n and ok_a):
        diffs.append((r["photo"][-40:], "research", res_n, res_acc, "service", svc_n, s["status"], r.get("source", "")))
n = len(rows)
print(f"same reading {same_read}/{n}, same accept decision {same_acc}/{n}")
for d in diffs:
    print("  differs:", *d)
acc = [r for r in rep["photos"] if r["status"] == "accepted"]
right = sum(lab[(p["file"].split("/", 1)[1])] == p["stripes"] for p in acc)
print(f"service on these photos (model trained on all 7 fields, so optimistic): accepted {len(acc)}, of which exact {right}")
sys.exit(0 if not diffs or all(d[-1] for d in diffs) else 1)
