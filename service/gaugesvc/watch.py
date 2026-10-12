"""Folder watcher: a zip copied into IN_DIR is read once its size stops changing; the report goes to
OUT_DIR/<zip>.report.json and the zip to IN_DIR/done (or IN_DIR/failed with OUT_DIR/<zip>.error.json)."""
import json, os, shutil, time
from pathlib import Path
from . import batch

IN = Path(os.environ.get("IN_DIR", "/data/in"))
OUT = Path(os.environ.get("OUT_DIR", "/data/out"))
POLL = float(os.environ.get("POLL_SECONDS", "10"))
HEARTBEAT = Path(os.environ.get("HEARTBEAT", "/tmp/heartbeat"))
SEEN = ".processed.json"           # fingerprints of zips already read, kept in OUT


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def _move(src, folder):
    folder.mkdir(parents=True, exist_ok=True)
    dst = folder / src.name
    if dst.exists():
        dst = folder / f"{src.stem}.{int(time.time())}{src.suffix}"
    shutil.move(str(src), str(dst))


def _write(path, data):
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)                              # a reader never sees a half-written report


class Watcher:
    def __init__(self, inp=IN, out=OUT):
        self.inp, self.out, self.sizes = Path(inp), Path(out), {}
        for d in (self.inp, self.out, self.inp / "done", self.inp / "failed"):
            d.mkdir(parents=True, exist_ok=True)
        f = self.out / SEEN
        self.seen = set(json.loads(f.read_text())) if f.exists() else set()

    def ready(self):
        """Zips whose size was the same on the last two looks (a copy in progress keeps growing)."""
        now = {p: p.stat().st_size for p in self.inp.glob("*.zip") if p.is_file()}
        stable = [p for p, s in now.items() if s > 0 and self.sizes.get(p) == s]
        self.sizes = now
        return sorted(stable)

    def handle(self, z):
        fp = batch.sha256(z)
        if fp in self.seen:
            log(f"{z.name}: already processed (same fingerprint), moved to done")
            _move(z, self.inp / "done")
            return "duplicate"
        log(f"{z.name}: reading")
        try:
            report = batch.run(z)
        except batch.ZipRejected as e:
            _write(self.out / f"{z.stem}.error.json", dict(zip=z.name, error=str(e)))
            _move(z, self.inp / "failed")
            log(f"{z.name}: failed: {e}")
            return "failed"
        _write(self.out / f"{z.stem}.report.json", report)
        self.seen.add(fp)
        _write(self.out / SEEN, sorted(self.seen))
        _move(z, self.inp / "done")
        s = report["summary"]
        log(f"{z.name}: {s['photos']} photos, {s['accepted']} accepted, {s['review']} review, "
            f"{s['no_gauge']} no gauge, {s['error']} error in {report['seconds']}s")
        return "done"

    def once(self):
        HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
        HEARTBEAT.write_text(str(time.time()))
        return [self.handle(z) for z in self.ready()]

    def forever(self):
        log(f"watching {self.inp} every {POLL:g}s -> {self.out}")
        while True:
            self.once()
            time.sleep(POLL)


def healthy(max_age=None):
    """Docker HEALTHCHECK: the loop wrote its heartbeat recently."""
    max_age = max_age or 3 * POLL + 600            # one long batch may hold the loop for minutes
    try:
        return time.time() - float(HEARTBEAT.read_text()) < max_age
    except (OSError, ValueError):
        return False
