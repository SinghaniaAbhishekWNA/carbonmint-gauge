"""Stamp the White Noise letterhead (logo right, company line left, hairline rule) on every page of a PDF.
The top band (0 to 52 pt) is painted white first, so a stray print header such as "Untitled" disappears.
  python scripts/letterhead.py in.pdf out.pdf [--skip-first] [--line "White Noise · ..."]
--skip-first leaves page 1 alone (for reports whose first page carries its own masthead).
Needs pypdf and Chrome (the stamp is drawn as HTML and printed to a transparent PDF)."""
import base64, io, os, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image
from pypdf import PdfReader, PdfWriter

LOGO = Path(os.environ.get("WN_LOGO", r"C:\Users\abhishek\Desktop\WN Logo 1200 x 1200.avif"))
CHROME = os.environ.get("CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def logo_uri():
    b = io.BytesIO()
    Image.open(LOGO).convert("RGBA").save(b, "PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def stamp_html(n, w_pt, h_pt, skip_first, line, left_pt, right_pt):
    pages = []
    for i in range(n):
        if skip_first and i == 0:
            pages.append('<div class="pg"></div>')
            continue
        pages.append(f'''<div class="pg"><div class="band"></div>
 <div class="line">{line}</div><img class="logo" src="{logo_uri()}" alt="">
 <div class="rule"></div></div>''')
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: {w_pt}pt {h_pt}pt; margin: 0; }}
html, body {{ margin: 0; background: transparent; }}
.pg {{ position: relative; width: {w_pt}pt; height: {h_pt}pt; page-break-after: always; overflow: hidden; }}
.band {{ position: absolute; left: 0; top: 0; width: 100%; height: 52pt; background: #fff; }}
.line {{ position: absolute; left: {left_pt}pt; top: 22pt; font: 600 8.5pt "Segoe UI", sans-serif; letter-spacing: .06em;
        text-transform: uppercase; color: #3a4440; }}
.logo {{ position: absolute; right: {w_pt - right_pt}pt; top: 9pt; width: 34pt; height: 34pt; }}
.rule {{ position: absolute; left: {left_pt}pt; right: {w_pt - right_pt}pt; top: 47pt; border-top: .75pt solid #1c2420; }}
</style></head><body>{"".join(pages)}</body></html>'''


def main():
    args = sys.argv[1:]
    src, dst = Path(args[0]), Path(args[1])
    skip = "--skip-first" in args
    line = args[args.index("--line") + 1] if "--line" in args else "White Noise &middot; CarbonMint water-gauge reader"
    left = float(args[args.index("--left") + 1]) if "--left" in args else 54
    right = float(args[args.index("--right") + 1]) if "--right" in args else 558
    rd = PdfReader(str(src))
    box = rd.pages[0].mediabox
    w, h = float(box.width), float(box.height)
    with tempfile.TemporaryDirectory() as td:
        html, pdf = Path(td) / "stamp.html", Path(td) / "stamp.pdf"
        html.write_text(stamp_html(len(rd.pages), w, h, skip, line, left, right), encoding="utf-8")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf}", html.as_uri()], check=True, capture_output=True)
        st = PdfReader(str(pdf))
        assert len(st.pages) == len(rd.pages), (len(st.pages), len(rd.pages))
        out = PdfWriter()
        for page, s in zip(rd.pages, st.pages):
            page.merge_page(s)
            out.add_page(page)
        out.add_metadata({"/Author": "White Noise", "/Title": line.replace("&middot;", "·")})
        with open(dst, "wb") as fh:
            out.write(fh)
    print(f"{len(rd.pages)} pages -> {dst}")


if __name__ == "__main__":
    main()
