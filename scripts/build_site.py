"""Builds the betadoc site from site/ templates -> public/ (index, documentation, app).
Numbers come from data/comparison.json; the Status rows are the BUILT features in docs/project_data.json only
(partial and roadmap features stay in the JSON until they are built and tested).
  python scripts/build_site.py [--app-url https://...]"""
import html, json, shutil, sys
from pathlib import Path

SITE, PUB = Path("site"), Path("public")
APP_URL = sys.argv[sys.argv.index("--app-url") + 1] if "--app-url" in sys.argv else "app.html"
NAMES = {"v0 (company, rebuilt)": "v0: current detector (rebuilt)", "Teammate (method 3)": "Colour method (team)",
         "Our reader, own score": "v1 reader, untrained confidence", "v1": "v1", "**v2**": "<b>v2</b>"}
CHAPTERS = [(0, "The gauge and the goal"), (10.6, "Three methods"), (28.1, "None was good enough"),
            (38.3, "v1: the best idea from each"), (53.0, "The company's rule"), (66.0, "Result: 72.4%"), (81.6, "Next"), (90.0, "Update: v2, 76.4%")]


def arch_svg():
    boxes = [("Drone photo", "JPEG, two shots a visit"), ("Find the rod", "ring stack, leaf gaps joined"),
             ("Straighten", "follow lean and bend"), ("Ring rhythm", "pitch, first to last ring"),
             ("Confidence", "trained P(exact)"), ("Checks", "bad gauge, two shots, spikes"), ("Accept ≥ 0.7", "cm, level, soil state")]
    w, h, gap, y = 150, 70, 22, 30
    W = len(boxes) * (w + gap) - gap + 20
    s = [f'<svg viewBox="0 0 {W} 190" width="{W}" height="190" role="img" aria-label="Pipeline: drone photo, find the rod, straighten, '
         'ring rhythm, confidence, checks, accept at 0.7 or send to review">',
         '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
         '<path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>']
    for i, (t, sub) in enumerate(boxes):
        x = 10 + i * (w + gap)
        hl = ' style="stroke:var(--brand);stroke-width:2.5"' if t.startswith("Confidence") else ""
        s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="var(--paper)" stroke="var(--line)" stroke-width="1.5"{hl}/>')
        s.append(f'<text x="{x + w / 2}" y="{y + 30}" text-anchor="middle" font-size="15" font-weight="700">{html.escape(t)}</text>')
        s.append(f'<text x="{x + w / 2}" y="{y + 52}" text-anchor="middle" font-size="11.5" style="fill:var(--mut)">{html.escape(sub)}</text>')
        if i:
            s.append(f'<line x1="{x - gap + 2}" y1="{y + h / 2}" x2="{x - 3}" y2="{y + h / 2}" stroke="currentColor" style="color:var(--mut)" stroke-width="1.6" marker-end="url(#ar)"/>')
    rx = 10 + 5 * (w + gap) + w / 2
    s.append(f'<path d="M{rx},{y + h} V150 H{rx + 200}" fill="none" stroke="var(--ring)" stroke-width="1.6" stroke-dasharray="5 4"/>')
    s.append(f'<text x="{rx + 10}" y="172" font-size="13" style="fill:var(--ring)">below 0.7 or flagged: a person reviews it</text>')
    s.append("</svg>")
    return "".join(s)


def results_rows():
    c = json.load(open("data/comparison.json"))
    pct = lambda a, b: f"{100 * a / b:.1f}%"
    rows = []
    for k, s in c.items():
        rows.append(f"<tr><td>{NAMES.get(k, html.escape(k))}</td><td><b>{s['acc_exact']}/{s['n']} = {pct(s['acc_exact'], s['n'])}</b></td>"
                    f"<td>{pct(s['acc'], s['n'])}</td><td>{pct(s['acc_exact'], max(s['acc'], 1))}</td><td>{pct(s['exact'], s['n'])}</td></tr>")
    return "".join(rows), c


def matrix():
    d = json.load(open("docs/project_data.json", encoding="utf-8"))
    built = [f for f in d["features"] if f["status"] == "built"]
    runs = {"local": "On-premises", "hybrid": "On-premises and hosted", "cloud": "Hosted"}
    return "".join(f"<tr><td>{html.escape(f['name'])}</td><td>{html.escape(f['gap'])}</td><td>{runs[f['runs']]}</td></tr>" for f in built), len(built)


def main():
    PUB.mkdir(exist_ok=True)
    (PUB / "media").mkdir(exist_ok=True)
    for name, src in (("crop-good.jpg", "docs/img/good.jpg"), ("crop-far.jpg", "docs/img/bad-far.jpg"), ("crop-blur.jpg", "docs/img/bad-blur.jpg")):
        shutil.copyfile(src, PUB / "media" / name)
    rows, c = results_rows()
    mrows, n = matrix()
    v0, v1 = c["v0 (company, rebuilt)"], c["**v2**"]
    fill = {"{{STYLE}}": (SITE / "_style.css").read_text(encoding="utf-8"), "{{THEME}}": (SITE / "_theme.js").read_text(encoding="utf-8"),
            "{{RESULTS_ROWS}}": rows, "{{MATRIX_ROWS}}": mrows, "{{BUILT_COUNT}}": str(n), "{{ARCH_SVG}}": arch_svg(),
            "{{V0_PCT}}": f"{100 * v0['acc_exact'] / v0['n']:.0f}%", "{{V1_PCT}}": f"{100 * v1['acc_exact'] / v1['n']:.0f}%",
            "{{APP_URL}}": json.dumps(APP_URL),
            "{{CHAPTERS}}": "".join(f'<li><button type="button" data-t="{t}">{html.escape(x)}</button></li>' for t, x in CHAPTERS)}
    for page in ("index.html", "documentation.html", "app.html"):
        t = (SITE / page).read_text(encoding="utf-8")
        for k, v in fill.items():
            t = t.replace(k, v)
        assert "{{" not in t, (page, t[t.index("{{"):t.index("{{") + 30])
        (PUB / page).write_text(t, encoding="utf-8")
    print(f"public/: index, documentation, app; {n} built features; v0 {fill['{{V0_PCT}}']} vs v2 {fill['{{V1_PCT}}']}; app url {APP_URL}")


if __name__ == "__main__":
    main()
