"""Evidence for method 3: per-set found rate for colour vs method-3 final, visit vote, states, end-to-end."""
import csv, subprocess, sys
for s in ("clear", "partial", "hard"):
    for m in ("colour", "method3final"):
        out = subprocess.run([sys.executable, "-P", "pipeline/evaluate.py", "locate", "--method", m, "--set", s], capture_output=True, text=True).stdout
        print(out.splitlines()[0])
print(subprocess.run([sys.executable, "-P", "pipeline/evaluate.py", "visits", "--methods", "colour,cascade,method3final"], capture_output=True, text=True).stdout)
from collections import Counter
r = list(csv.DictReader(open("results/locate_method3final.csv")))
print("method-3 states:", dict(Counter(x["state"] for x in r)))
