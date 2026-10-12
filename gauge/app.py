"""P6.1.1-2 Local review page (loopback only). Drop a visit folder -> readings table; correct a flagged visit;
export CSV.  python -m gauge.app [port]   (default 8090)
Routes: GET /  ·  POST /api/read?visit=<folder>&name=<file> (raw JPEG body)  ·  GET /api/visits
        POST /api/correct {visit, rings}  ·  GET /api/export.csv"""
import csv, io, json, re, sys, threading
from collections import defaultdict
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import numpy as np
from PIL import Image
from .detect import detect
from .measure import read
from .fuse import fuse, timeline

MAX_BYTES, MAX_PHOTOS = 40 << 20, 500
CORR = Path("data/corrections.csv")
reads = defaultdict(list)          # visit -> [dict(name, rings, confidence)]
lock = threading.Lock()

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gauge review</title><link rel="icon" href="data:,"><style>
:root{--bg:#f6f7f5;--fg:#17201a;--mut:#5b665f;--card:#fff;--line:#d9ded9;--warn:#9a5b00;--ok:#1d6b35}
@media (prefers-color-scheme:dark){:root{--bg:#0e1712;--fg:#e6ece7;--mut:#9aa69e;--card:#16211b;--line:#2a372f;--warn:#f2a93b;--ok:#7bd88f}}
body{margin:0;font:15px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--fg)}main{max-width:960px;margin:0 auto;padding:16px}
h1{font-size:20px}label.drop{display:block;border:2px dashed var(--line);border-radius:10px;padding:20px;background:var(--card);cursor:pointer}
table{width:100%;border-collapse:collapse;margin-top:16px;background:var(--card)}td,th{padding:8px;border-bottom:1px solid var(--line);text-align:left}
.flag{color:var(--warn)}.ok{color:var(--ok)}input[type=number]{width:5em}button{min-height:36px}#status{color:var(--mut)}a{color:inherit}
</style></head><body><main><h1>Water-gauge review</h1>
<label class="drop">Choose a visit folder (or several photos) <input id="files" type="file" accept="image/jpeg" multiple webkitdirectory></label>
<p id="status">No photos yet.</p><p><a href="/api/export.csv">Download CSV</a></p>
<table><thead><tr><th>Visit</th><th>Rings</th><th>Confidence</th><th>Flags</th><th>Correct</th></tr></thead><tbody id="rows"></tbody></table>
<script>
const $=s=>document.querySelector(s);
async function refresh(){const v=await (await fetch('/api/visits')).json();$('#rows').innerHTML='';
 for(const o of v){const tr=document.createElement('tr');
  tr.innerHTML=`<td></td><td>${o.rings??'-'}</td><td>${o.confidence}</td><td class="${o.flags.length?'flag':'ok'}">${o.flags.join('; ')||'ok'}</td>`+
  `<td><input type="number" step="0.5" min="0" max="40" aria-label="Corrected rings"> <button>Save</button></td>`;
  tr.cells[0].textContent=o.visit;
  tr.querySelector('button').onclick=async()=>{const r=tr.querySelector('input').value;if(r==='')return;
   const res=await fetch('/api/correct',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({visit:o.visit,rings:Number(r)})});
   $('#status').textContent=res.ok?'Correction saved.':'Correction rejected.';refresh();};
  $('#rows').appendChild(tr);}}
$('#files').onchange=async e=>{const fs=[...e.target.files].filter(f=>/\.jpe?g$/i.test(f.name));let n=0;
 for(const f of fs){const parts=(f.webkitRelativePath||f.name).split('/');const visit=parts.length>1?parts[parts.length-2]:'upload';
  $('#status').textContent=`Reading ${++n}/${fs.length}…`;
  await fetch(`/api/read?visit=${encodeURIComponent(visit)}&name=${encodeURIComponent(f.name)}`,{method:'POST',body:f});}
 $('#status').textContent=`${fs.length} photos read.`;refresh();};
refresh();
</script></main></body></html>"""


def visits():
    with lock:
        items = {v: list(rs) for v, rs in reads.items()}
    corr = {}
    if CORR.exists():
        with open(CORR, newline="") as fh:
            for r in csv.DictReader(fh):
                corr[r["visit"]] = float(r["rings"])
    out = []
    for v, rs in sorted(items.items()):
        f = fuse(rs)
        m = re.search(r"(\d{2})(\d{2})(\d{2})\d{6}$", v)
        out.append(dict(visit=v, plot="-".join(v.rsplit(" - ", 1)[0].split("-")[:4]),
                        date=f"20{m[3]}-{m[2]}-{m[1]}" if m else "", rings=corr.get(v, f["rings"]),
                        confidence=round(f["confidence"], 2), flags=["corrected"] if v in corr else f["flags"], photos=len(rs)))
    for plot in {o["plot"] for o in out}:
        seq = sorted((o for o in out if o["plot"] == plot), key=lambda o: o["date"])
        for o, fl in zip(seq, timeline([o["rings"] for o in seq])):
            if fl and "corrected" not in o["flags"]:
                o["flags"].append("timeline spike")
    return out


class H(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        self.send_header("X-Content-Type-Options", "nosniff"); self.end_headers(); self.wfile.write(b)

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self.send(200, PAGE, "text/html; charset=utf-8")
        if u.path == "/api/visits":
            return self.send(200, json.dumps(visits()))
        if u.path == "/api/export.csv":
            s = io.StringIO(); w = csv.writer(s)
            w.writerow(["plot", "date", "visit", "rings", "confidence", "flag"])
            for o in visits():
                w.writerow([o["plot"], o["date"], o["visit"], o["rings"], o["confidence"], "; ".join(o["flags"])])
            return self.send(200, s.getvalue(), "text/csv; charset=utf-8")
        self.send(404, '{"error":"not found"}')

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BYTES:
            return self.send(413, '{"error":"empty or too large"}')
        body = self.rfile.read(n)
        if u.path == "/api/read":
            q = parse_qs(u.query)
            visit, name = q.get("visit", ["upload"])[0][:120], q.get("name", ["photo.jpg"])[0][:120]
            if body[:3] != b"\xff\xd8\xff":
                return self.send(415, '{"error":"JPEG only"}')
            with lock:
                if sum(map(len, reads.values())) >= MAX_PHOTOS:
                    return self.send(429, '{"error":"photo limit reached"}')
            try:
                im = np.asarray(Image.open(io.BytesIO(body)).convert("RGB")).astype(np.int16)
            except Exception:
                return self.send(400, '{"error":"unreadable image"}')
            det = detect(im)
            r = read(im, det) if det else dict(rings=None, confidence=0.0)
            with lock:
                reads[visit].append(dict(name=name, rings=r["rings"], confidence=r["confidence"]))
            return self.send(200, json.dumps(dict(visit=visit, name=name, rings=r["rings"], confidence=r["confidence"])))
        if u.path == "/api/correct":
            try:
                d = json.loads(body); v, rings = str(d["visit"])[:120], float(d["rings"])
            except Exception:
                return self.send(400, '{"error":"need visit and rings"}')
            if not 0 <= rings <= 40 or v not in reads:
                return self.send(400, '{"error":"unknown visit or rings out of range"}')
            new = not CORR.exists()
            CORR.parent.mkdir(exist_ok=True)
            with open(CORR, "a", newline="") as fh:
                w = csv.writer(fh)
                if new:
                    w.writerow(["visit", "rings", "saved_at"])
                w.writerow([v, rings, datetime.now().isoformat(timespec="seconds")])
            return self.send(200, '{"ok":true}')
        self.send(404, '{"error":"not found"}')


def main(port=8090):
    srv = ThreadingHTTPServer(("127.0.0.1", int(port)), H)
    print(f"review page on http://127.0.0.1:{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main(*sys.argv[1:])
