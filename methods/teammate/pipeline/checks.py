"""Small data checks that back the P0 leaves (so they can be re-run and screenshotted).

python pipeline/checks.py sort     P0.1.1 photo counts per visibility class
python pipeline/checks.py counts   P0.1.2 manual ring counts present for every clear photo
python pipeline/checks.py points   P0.1.3 hand-marked pipe points present for all photos
"""
import csv, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
rows = list(csv.DictReader(open(ROOT / "sorted/visibility_labels.csv", encoding="utf-8")))
what = sys.argv[1] if len(sys.argv) > 1 else ""
ok = False
if what == "sort":
    want = {"1_clear": 59, "2_partial": 44, "3_hard": 25}
    got = {d: len(list((ROOT / "sorted" / d).glob("*.jpg"))) for d in want}
    for d in want:
        print(f"{d:10s} files={got[d]:3d}  expected={want[d]}")
    print("csv rows:", len(rows))
    ok = got == want and len(rows) == 128
elif what == "counts":
    clear = [r for r in rows if r["class"] == "1_clear"]
    have = [r for r in clear if r["rings_visible"] != "" and r["count_conf"] != ""]
    print(f"clear rows {len(clear)}, with rings_visible + count_conf {len(have)}")
    print("exact:", sum(r["count_conf"] == "exact" for r in have), " est:", sum(r["count_conf"] == "est" for r in have))
    ok = len(clear) == 59 and len(have) == 59
elif what == "points":
    pts = list(csv.DictReader(open(ROOT / "data/pipe_points.csv")))
    print("pipe_points.csv rows:", len(pts), " unsure:", [p["idx"] for p in pts if p["certainty"] == "unsure"])
    ok = len(pts) == 128 and {int(p["idx"]) for p in pts} == set(range(128))
else:
    sys.exit(__doc__)
print("RESULT", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
