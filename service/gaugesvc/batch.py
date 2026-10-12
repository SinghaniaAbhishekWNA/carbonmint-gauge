"""One zip -> one report. Photos are read straight out of the zip (never unpacked); the folder a photo sits in is
its visit (<checkpoint> - <ddmmyyHHMMSS>), so the two shots of a visit are read together."""
import hashlib, os, re, time, zipfile
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor
from pathlib import PurePosixPath
from . import engine

VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
MAX_IMAGES = int(os.environ.get("MAX_IMAGES", "5000"))
MAX_PHOTO_BYTES = int(os.environ.get("MAX_PHOTO_MB", "60")) * 2**20
WORKERS = int(os.environ.get("WORKERS", "1"))
VISIT_MAX = 4                       # a folder with more photos than this is not one visit: read each on its own
PHOTO_EXT = {".jpg", ".jpeg", ".png"}
VISIT_RE = re.compile(r"^(?P<checkpoint>.+?) - (?P<stamp>\d{12})$")


class ZipRejected(Exception):
    pass


def safe(name):
    """A member name is used only if it stays inside the zip's own folder tree."""
    p = PurePosixPath(name.replace("\\", "/"))
    return not (p.is_absolute() or ".." in p.parts or re.match(r"^[A-Za-z]:", name))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(2**20), b""):
            h.update(chunk)
    return h.hexdigest()


def plan(zf):
    """Group photo members into visits. Returns (visits {key: [names]}, skipped [names with reasons])."""
    groups, skipped = OrderedDict(), []
    for info in zf.infolist():
        if info.is_dir():
            continue
        n = info.filename
        if not safe(n):
            skipped.append(dict(name=n, reason="unsafe path"))
        elif PurePosixPath(n).suffix.lower() not in PHOTO_EXT:
            skipped.append(dict(name=n, reason="not a jpg or png"))
        elif info.file_size > MAX_PHOTO_BYTES:
            skipped.append(dict(name=n, reason="photo too large"))
        else:
            groups.setdefault(str(PurePosixPath(n).parent), []).append(n)
    total = sum(len(v) for v in groups.values())
    if total == 0:
        raise ZipRejected("no jpg or png photos in the zip")
    if total > MAX_IMAGES:
        raise ZipRejected(f"{total} photos is more than MAX_IMAGES={MAX_IMAGES}")
    visits = OrderedDict()
    for folder, names in groups.items():
        names.sort()
        m = VISIT_RE.match(PurePosixPath(folder).name)
        if m and len(names) <= VISIT_MAX:
            visits[folder] = names
        else:                                           # loose photos or a non-visit folder: each on its own
            for n in names:
                visits[n] = [n]
    return visits, skipped


def _read_visit(args):
    zpath, names = args
    with zipfile.ZipFile(zpath) as zf:
        rows = []
        for n in names:
            try:
                rows.append(engine.measure(zf.read(n)))
            except Exception as e:                      # e.g. a corrupt member (bad CRC)
                rows.append(dict(error=f"cannot read from zip: {type(e).__name__}"))
    return engine.visit(rows)


def run(zpath, zip_name=None, on_visit=None):
    t0 = time.time()
    try:
        zf = zipfile.ZipFile(zpath)
    except (zipfile.BadZipFile, OSError) as e:
        raise ZipRejected(f"not a readable zip: {type(e).__name__}")
    with zf:
        visits, skipped = plan(zf)
    jobs = [(str(zpath), names) for names in visits.values()]
    if WORKERS > 1:
        with ProcessPoolExecutor(WORKERS) as ex:
            results = list(ex.map(_read_visit, jobs))
    else:
        results = []
        for j in jobs:
            results.append(_read_visit(j))
            if on_visit:
                on_visit()                              # keeps the health check alive through long batches
    photos, vis = [], []
    for (key, names), res in zip(visits.items(), results):
        m = VISIT_RE.match(PurePosixPath(names[0]).parent.name)
        reading, consistent = engine.visit_reading(res)
        vis.append(dict(folder=str(PurePosixPath(names[0]).parent), checkpoint=m["checkpoint"] if m else None,
                        taken=_stamp(m["stamp"]) if m else None, photos=names, reading=reading, consistent=consistent))
        for n, r in zip(names, res):
            photos.append(dict(file=n, visit=str(PurePosixPath(n).parent), **r))
    count = lambda s: sum(p["status"] == s for p in photos)
    return dict(
        schema_version=SCHEMA_VERSION,
        engine=dict(name="CarbonMint gauge reader", version=VERSION, commit=os.environ.get("GIT_COMMIT", "unknown")),
        service="CarbonMint gauge reader v1", zip=zip_name or os.path.basename(zpath), sha256=sha256(zpath),
        processed_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"), seconds=round(time.time() - t0, 1),
        settings=dict(cm_per_stripe=engine.CM_PER_STRIPE, accept_at=0.7, guide_zero_cm=10),
        summary=dict(photos=len(photos), accepted=count("accepted"), review=count("review"), no_gauge=count("no_gauge"),
                     error=count("error"), visits=len(vis), skipped=len(skipped)),
        visits=vis, photos=photos, skipped=skipped)


def _stamp(s):
    """ddmmyyHHMMSS -> ISO date-time (no time zone: the folder name carries none)."""
    return f"20{s[4:6]}-{s[2:4]}-{s[0:2]}T{s[6:8]}:{s[8:10]}:{s[10:12]}"
