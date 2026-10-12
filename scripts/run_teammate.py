"""Run the teammate's method 3 final (vendored, unchanged) on our photos.
Links our photos into the layout their code expects (methods/teammate/sorted/<class>/<idx>__<folder>__<file>),
then runs their pipeline. Needs opencv-python-headless. Their photo #93 is not in our folder and is skipped."""
import csv, os, subprocess, sys
from pathlib import Path

T = Path("methods/teammate")


def link():
    rows = list(csv.DictReader(open(T / "sorted/visibility_labels.csv", encoding="utf-8")))
    for r in rows:
        src = Path("way points") / r["checkpoint_folder"] / r["file"]
        d = T / "sorted" / r["class"]
        d.mkdir(parents=True, exist_ok=True)
        dst = d / f'{int(r["idx"]):03d}__{r["checkpoint_folder"].replace(" ", "_")}__{r["file"]}'
        if not dst.exists():
            os.link(src, dst)
    print(f"{len(rows)} photos linked")


def main():
    link()
    steps = [["pipeline/locate.py", "--method", "colour"], ["pipeline/locate.py", "--method", "hybrid"],
             ["pipeline/locate.py", "--method", "colour", "--wb"], ["pipeline/align.py", "method3", "colour_wb"],
             ["pipeline/align.py", "final"], ["pipeline/rings.py", "--method", "method3final"]]
    for s in steps:
        print(">", " ".join(s), flush=True)
        subprocess.run([sys.executable, *s], cwd=T, check=True)


if __name__ == "__main__":
    main()
