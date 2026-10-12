"""Demo app (WSGI, stdlib only): PIN sign-in with roles, the 127-photo gallery with every method's reading, a live
v1 read of an uploaded photo, corrections and CSV export. The same `app` runs locally (python -m gauge.web [port])
and on Vercel (root app.py). Static pages in public/ are served by Vercel directly, and by this app locally.

Roles: admin does everything; user can view, upload and correct. Every /api route declares its role below."""
import base64, csv, hashlib, hmac, io, json, mimetypes, os, re, secrets, threading, time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[1]
PUBLIC, PRIVATE = ROOT / "public", ROOT / "media_private" / "photos"
GALLERY = json.loads((ROOT / "data" / "gallery.json").read_text())
SESSION_H, LOCK_TRIES, LOCK_S = 8 * 3600, 5, 60
MAX_UPLOAD = int(os.environ.get("CM_MAX_UPLOAD", 4_400_000))      # Vercel caps a request at 4.5 MB
CLOUD = os.environ.get("CM_CLOUD") == "1"                          # hosted lane: corrections are not kept


def _load_env(f=ROOT / ".env"):
    """Local lane: read KEY=VALUE lines from the gitignored .env (PM2 runs as SYSTEM and sees no user env).
    Values already in the environment win, so the hosted lane's encrypted env is never overridden."""
    if f.exists():
        for line in f.read_text().splitlines():
            k, sep, v = line.strip().partition("=")
            if sep and k and not k.startswith("#"):
                os.environ.setdefault(k.strip(), v.strip())


_load_env()


def _secret():
    s = os.environ.get("CM_SECRET")
    if s:
        return s.encode()
    f = ROOT / "data" / ".secret"                                 # local lane: generated once, gitignored
    if not f.exists():
        f.parent.mkdir(exist_ok=True)
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip().encode()


SECRET = _secret()
def _pins():
    """PINs come only from the environment (local .env or the host's encrypted env); there is no default."""
    a, u = os.environ.get("CM_ADMIN_PIN", ""), os.environ.get("CM_USER_PIN", "")
    if len(a) < 6 or len(u) < 6 or a == u:
        raise RuntimeError("set CM_ADMIN_PIN and CM_USER_PIN (6+ characters each, different) before starting the demo")
    return {a: "admin", u: "user"}


PINS = _pins()
_fails, _lock = {}, threading.Lock()


def sign(role, now=None):
    now = time.time() if now is None else now
    body = base64.urlsafe_b64encode(json.dumps(dict(role=role, exp=int(now + SESSION_H))).encode()).decode()
    return body + "." + hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()


def verify(tok, now=None):
    now = time.time() if now is None else now
    try:
        body, sig = tok.rsplit(".", 1)
        if not hmac.compare_digest(sig, hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()):
            return None
        d = json.loads(base64.urlsafe_b64decode(body))
        return d["role"] if d["exp"] > now and d["role"] in ("admin", "user") else None
    except Exception:
        return None


def role_of(env):
    for part in env.get("HTTP_COOKIE", "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == "cm_session":
            return verify(v)
    return None


# ---- the v2 reader, loaded on first use (numpy/scipy are heavy) ----------------------------------------
_model = None


def read_v1(data):
    global _model
    import numpy as np
    from PIL import Image
    from .detect import detect
    from .measure import read
    from . import v1
    if _model is None:
        _model = v1.Model.from_json((ROOT / "models" / "v2_confidence.json").read_text())
    im = np.asarray(Image.open(io.BytesIO(data)).convert("RGB")).astype(np.int16)
    det = detect(im)
    if det is None:
        return dict(cm=None, confidence=0.0, accepted=False, note="no gauge found", size=[im.shape[1], im.shape[0]])
    r = read(im, det)
    row = {k: ("" if v is None else v) for k, v in r.items()}
    row["half"] = det["half"]
    p = float(_model.prob(v1.features(row, [])[None, :])[0])            # one photo: no sibling shot to compare
    d = v1.decide(row, p)
    d["mark"] = None if r["first_y"] is None else dict(x=round(float(det["center"][0])), first=r["first_y"],
                                                         last=r["last_y"], half=round(det["half"]))
    d["size"] = [im.shape[1], im.shape[0]]
    d["pitch_px"] = r["pitch_px"]
    return d


# ---- routes ------------------------------------------------------------------------------------------------
def j(start, code, obj, headers=()):
    b = json.dumps(obj).encode()
    start(f"{code} {'OK' if code < 400 else 'ERROR'}", [("Content-Type", "application/json"), ("Content-Length", str(len(b))),
                                                       ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"), *headers])
    return [b]


def body_of(env, limit):
    n = int(env.get("CONTENT_LENGTH") or 0)
    if n <= 0 or n > limit:
        return None
    return env["wsgi.input"].read(n)


def api(env, start, path, method, role):
    # ROUTE                         ROLE
    # GET  /api/me                  public (role null when signed out)
    # POST /api/login               public
    # POST /api/logout              public
    # GET  /api/gallery             user
    # GET  /api/photo/<id>.jpg      user
    # POST /api/read                user
    # POST /api/correct             user
    # GET  /api/corrections         admin
    # GET  /api/export.csv          admin
    need = {"/api/gallery": "user", "/api/read": "user", "/api/correct": "user",
            "/api/corrections": "admin", "/api/export.csv": "admin"}.get(path, "user" if path.startswith("/api/photo/") else None)
    if need and role is None:
        return j(start, 401, dict(error="sign in first"))
    if need == "admin" and role != "admin":
        return j(start, 403, dict(error="admin only"))

    if path == "/api/me":
        return j(start, 200, dict(role=role, cloud=CLOUD, max_upload=MAX_UPLOAD))
    if path == "/api/login" and method == "POST":
        ip = env.get("HTTP_X_FORWARDED_FOR", env.get("REMOTE_ADDR", "?")).split(",")[0].strip()
        with _lock:
            n, until = _fails.get(ip, (0, 0))
            if until > time.time():
                return j(start, 429, dict(error=f"too many wrong PINs; wait {int(until - time.time()) + 1} s"))
        raw = body_of(env, 1000)
        try:
            pin = str(json.loads(raw or b"{}").get("pin", ""))
        except Exception:
            pin = ""
        r = next((v for k, v in PINS.items() if hmac.compare_digest(k, pin)), None)
        with _lock:
            if r is None:
                n = _fails.get(ip, (0, 0))[0] + 1
                _fails[ip] = (0, time.time() + LOCK_S) if n >= LOCK_TRIES else (n, 0)
                return j(start, 401, dict(error="wrong PIN"))
            _fails.pop(ip, None)
        secure = "; Secure" if env.get("HTTP_X_FORWARDED_PROTO", env.get("wsgi.url_scheme")) == "https" else ""
        return j(start, 200, dict(role=r), [("Set-Cookie", f"cm_session={sign(r)}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_H}{secure}")])
    if path == "/api/logout" and method == "POST":
        return j(start, 200, dict(ok=True), [("Set-Cookie", "cm_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")])
    if path == "/api/gallery":
        return j(start, 200, GALLERY)
    m = re.fullmatch(r"/api/photo/(\d{3})\.jpg", path)
    if m:
        f = PRIVATE / f"{m[1]}.jpg"                                  # digits only: no path traversal
        if not f.exists():
            return j(start, 404, dict(error="no such photo"))
        b = f.read_bytes()
        start("200 OK", [("Content-Type", "image/jpeg"), ("Content-Length", str(len(b))), ("Cache-Control", "private, max-age=3600")])
        return [b]
    if path == "/api/read" and method == "POST":
        data = body_of(env, MAX_UPLOAD)
        if data is None:
            return j(start, 413, dict(error=f"send one JPEG up to {MAX_UPLOAD // 1_000_000} MB"))
        if data[:3] != b"\xff\xd8\xff":
            return j(start, 415, dict(error="JPEG only"))
        try:
            return j(start, 200, read_v1(data))
        except Exception as e:
            return j(start, 400, dict(error=f"could not read this photo ({type(e).__name__})"))
    if path == "/api/correct" and method == "POST":
        try:
            d = json.loads(body_of(env, 2000) or b"{}")
            pid, rings = str(d["id"]), float(d["rings"])
        except Exception:
            return j(start, 400, dict(error="need id and rings"))
        if not re.fullmatch(r"\d{3}|upload", pid) or not 0 <= rings <= 40:
            return j(start, 400, dict(error="bad id or rings out of range"))
        if CLOUD:
            return j(start, 200, dict(ok=True, kept=False, note="hosted demo: corrections are not stored"))
        f = ROOT / "data" / "corrections.csv"
        new = not f.exists()
        with _lock, open(f, "a", newline="") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["id", "rings", "role", "saved_at"])
            w.writerow([pid, rings, role, datetime.now().isoformat(timespec="seconds")])
        return j(start, 200, dict(ok=True, kept=True))
    if path == "/api/corrections":
        f = ROOT / "data" / "corrections.csv"
        rows = list(csv.DictReader(open(f, newline=""))) if f.exists() else []
        return j(start, 200, dict(corrections=rows))
    if path == "/api/export.csv":
        s = io.StringIO(); w = csv.writer(s)
        w.writerow(["id", "plot", "visit", "date", "shot", "v2_cm", "v2_confidence", "v2_accepted", "v2_note", "v1_cm", "v1_confidence", "v1_accepted", "v1_note", "v0_cm", "v0_accepted", "label"])
        for p in GALLERY["photos"]:
            w.writerow([p["id"], p["plot"], p["visit"], p["date"], p["shot"], p["v2"]["cm"], p["v2"]["confidence"],
                        int(p["v2"]["accepted"]), p["v2"]["note"], p["v1"]["cm"], p["v1"]["confidence"],
                        int(p["v1"]["accepted"]), p["v1"]["note"], p["v0"]["cm"], int(p["v0"]["accepted"]), p["label"]])
        b = s.getvalue().encode()
        start("200 OK", [("Content-Type", "text/csv; charset=utf-8"), ("Content-Length", str(len(b))),
                         ("Content-Disposition", "attachment; filename=carbonmint_v2.csv")])
        return [b]
    return j(start, 404, dict(error="not found"))


def app(env, start):
    path, method = env.get("PATH_INFO", "/"), env.get("REQUEST_METHOD", "GET")
    if path.startswith("/api/"):
        return api(env, start, path, method, role_of(env))
    # local lane only: serve the static site (Vercel serves public/ itself)
    if path == "/":
        path = "/index.html"
    f = (PUBLIC / path.lstrip("/")).resolve()
    if PUBLIC.resolve() not in f.parents or not f.is_file():
        return j(start, 404, dict(error="not found"))
    b = f.read_bytes()
    rng = env.get("HTTP_RANGE", "")
    m = re.fullmatch(r"bytes=(\d+)-(\d*)", rng)
    ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
    if m:                                                           # video seeking needs range requests
        a = int(m[1]); z = min(int(m[2]) if m[2] else len(b) - 1, len(b) - 1)
        start("206 Partial Content", [("Content-Type", ctype), ("Content-Range", f"bytes {a}-{z}/{len(b)}"),
                                      ("Accept-Ranges", "bytes"), ("Content-Length", str(z - a + 1))])
        return [b[a:z + 1]]
    start("200 OK", [("Content-Type", ctype), ("Content-Length", str(len(b))), ("Accept-Ranges", "bytes")])
    return [b]


def main(port=6900):
    from socketserver import ThreadingMixIn
    from wsgiref.simple_server import make_server, WSGIServer, WSGIRequestHandler

    class Server(ThreadingMixIn, WSGIServer):
        daemon_threads = True

    class Quiet(WSGIRequestHandler):
        def log_message(self, *a):
            pass

    srv = make_server("127.0.0.1", int(port), app, server_class=Server, handler_class=Quiet)
    print(f"CarbonMint demo on http://127.0.0.1:{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    import sys
    main(*sys.argv[1:])
