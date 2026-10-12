"""Run an acceptance test and save a screenshot of it as evidence.

python pipeline/evidence.py <leaf> [--attach img1,img2,...] -- <command ...>

Writes evidence/<leaf>_<YYYYmmdd-HHMMSS>.png (terminal-style render of command + output + exit code,
with any attached result images stacked underneath) and a .txt with the raw output.
Exits with the command's exit code.
"""
import datetime, pathlib, subprocess, sys
import cv2, numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
FONT, SCALE, LH, CW = cv2.FONT_HERSHEY_SIMPLEX, 0.5, 20, 9.2  # line height / approx char width in px


ASCII = {"✅": "[ok]", "❌": "[x]", "⚠️": "[!]", "⚠": "[!]", "₹": "Rs ", "→": "->", "≥": ">=", "≤": "<=", "±": "+/-",
         "÷": "/", "—": "-", "–": "-", "·": "|", "ρ": "rho", "−": "-", "×": "x", "…": "...", "️": ""}


def to_ascii(l):
    for k, v in ASCII.items():
        l = l.replace(k, v)
    return l.encode("ascii", "replace").decode()


def render_text(lines, width=1400):
    lines = [to_ascii(l).expandtabs(4) for l in lines]
    wrapped = []
    per = int((width - 30) / CW)
    for l in lines:
        wrapped += [l[k:k + per] for k in range(0, max(len(l), 1), per)]
    img = np.full((LH * len(wrapped) + 30, width, 3), (30, 30, 30), np.uint8)
    for n, l in enumerate(wrapped):
        col = (120, 220, 120) if "PASS" in l or l.startswith("$") else (90, 90, 240) if "FAIL" in l or "MISS" in l else (225, 225, 225)
        cv2.putText(img, l, (15, 22 + n * LH), FONT, SCALE, col, 1, cv2.LINE_AA)
    return img


def main():
    a = sys.argv[1:]
    if "--" not in a or not a:
        sys.exit(__doc__)
    leaf, sep = a[0], a.index("--")
    cmd = a[sep + 1:]
    attach = []
    if "--attach" in a[:sep]:
        attach = [p for p in a[a.index("--attach") + 1].split(",") if p]
    ts = datetime.datetime.now()
    import os
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    out = (r.stdout + r.stderr).rstrip().splitlines()
    head = [f"evidence for {leaf}  |  {ts:%Y-%m-%d %H:%M:%S}  |  {ROOT}", "", "$ " + " ".join(cmd)]
    lines = head + out + ["", f"exit code {r.returncode}"]
    panels = [render_text(lines)]
    for p in attach:
        im = cv2.imdecode(np.fromfile(str(ROOT / p), np.uint8), cv2.IMREAD_COLOR)
        if im is None:
            panels.append(render_text([f"(attachment not found: {p})"]))
            continue
        im = cv2.resize(im, (1400, round(im.shape[0] * 1400 / im.shape[1])))
        panels += [render_text([f"attached: {p}"]), im]
    dst = ROOT / "evidence"
    dst.mkdir(exist_ok=True)
    stem = f"{leaf}_{ts:%Y%m%d-%H%M%S}"
    cv2.imwrite(str(dst / f"{stem}.png"), np.vstack(panels))
    (dst / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(to_ascii("\n".join(out)))
    print(f"evidence -> evidence/{stem}.png")
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
