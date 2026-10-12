"""v1 on in-memory photos: the same reader, model and rules as the research code (gauge/), so the service gives
the same answers. One visit at a time, because the two shots of a visit check each other."""
import io, json, os, sys
from pathlib import Path
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]                              # repo checkout; in the image everything sits under /app
sys.path.insert(0, str(REPO))
from gauge.detect import detect                     # noqa: E402
from gauge.measure import read                      # noqa: E402
from gauge import v1                                # noqa: E402

MODEL_PATH = Path(os.environ.get("MODEL_PATH", REPO / "models" / "v2_confidence.json"))
COLOUR_DIR = Path(os.environ.get("COLOUR_DIR", REPO / "methods" / "teammate" / "pipeline"))
CM_PER_STRIPE = float(os.environ.get("CM_PER_STRIPE", "1.0"))
_model = None


def model():
    global _model
    if _model is None:
        _model = v1.Model.from_json(MODEL_PATH.read_text())
    return _model


def colour_locate(data):
    """Our colour method's locator, used only when the rod finder sees nothing. Returns a ring count
    (0 = dry) or None. Needs OpenCV; decodes with OpenCV exactly as the colour method does."""
    import cv2
    if str(COLOUR_DIR) not in sys.path:
        sys.path.insert(0, str(COLOUR_DIR))
    import isolate as I, locate as L, rings as R
    bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        return None, None
    sc = 1000 / bgr.shape[1]
    small = cv2.resize(bgr, (1000, round(bgr.shape[0] * sc)), interpolation=cv2.INTER_AREA)
    box = None
    for pre in (I.normalize, None):                     # brightness evened out first (as the colour method does)
        I.PREPROCESS = pre
        try:
            box = L.locate(small, "colour")["box"]
        finally:
            I.PREPROCESS = None
        if box is not None:
            break
    if box is None:
        return None, None
    box = [round(v / sc) for v in box]
    state, _, n = R.read(bgr, box)
    if state == "unreadable":
        return None, box
    return float(0 if state == "dry" else n), box


def decode(data):
    im = Image.open(io.BytesIO(data))
    im.load()
    return np.asarray(im.convert("RGB")).astype(np.int16)


def gauge_box(det):
    c, d, h = np.array(det["center"]), np.array(det["dir"]), det["half"]
    ends = [c + d * det["t0"], c + d * det["t1"]]
    xs, ys = [e[0] for e in ends], [e[1] for e in ends]
    return [round(min(xs) - 2 * h), round(min(ys)), round(max(xs) + 2 * h), round(max(ys))]


def measure(data):
    """Reader output for one photo, before the visit vote. Never raises: a bad photo comes back as an error row."""
    try:
        im = decode(data)
    except Exception as e:                               # damaged or not an image
        return dict(error=f"cannot read image: {type(e).__name__}")
    det = detect(im)
    if det is None:
        n, box = colour_locate(data)
        row = dict(rings="", box=box)
        if n is not None:
            row = dict(v1.fallback(row, {"state": "dry" if n == 0 else "counted", "rings": n}), box=box)
        return row
    r = read(im, det)
    row = {k: ("" if v is None else v) for k, v in r.items()}
    row.update(half=det["half"], box=gauge_box(det))
    return row


def level(stripes):
    if stripes is None:
        return None, None, None
    cm = round(stripes * CM_PER_STRIPE, 1)
    rel, state = v1.soil(cm)
    return cm, round(rel, 1), state


def visit(rows):
    """rows: measure() outputs for the shots of one visit (in order). Returns one result dict per shot."""
    out = []
    for i, r in enumerate(rows):
        if "error" in r:
            out.append(dict(status="error", error=r["error"], flags=[]))
            continue
        sibs = [s.get("rings", "") for j, s in enumerate(rows) if j != i and "error" not in s]
        flags = []
        if len(rows) < 2:
            flags.append("no_twin_shot")
        elif not any(s not in ("", None) for s in sibs):
            flags.append("twin_unreadable")
        if r.get("source"):
            flags.append("colour_locator_used")
        if r.get("rings") in ("", None):
            out.append(dict(status="no_gauge", stripes=None, confidence=0.0, gauge_box=r.get("box"), flags=flags))
            continue
        p = float(model().prob(v1.features(r, sibs)[None, :])[0])
        d = v1.decide(r, p)
        if d["note"].startswith("bad gauge"):
            flags.append("bad_gauge")
        n = float(r["rings"])
        res = dict(status="accepted" if d["accepted"] else "review", confidence=d["confidence"],
                   gauge_box=r.get("box"), flags=flags)
        if d["accepted"]:
            cm, rel, state = level(n)
            res.update(stripes=int(n), dry=n == 0, level_cm=cm, level_vs_guide_cm=rel, soil_state=state)
        else:
            res.update(stripes=None, candidate_stripes=int(n), note=d["note"])
        out.append(res)
    return out


def visit_reading(results):
    """Company folder rule: mean of the accepted shots; none accepted -> review."""
    acc = [r["stripes"] for r in results if r["status"] == "accepted"]
    if not acc:
        return dict(status="review", stripes=None, level_cm=None, soil_state=None), None
    s = round(sum(acc) / len(acc), 1)
    cm, rel, state = level(s)
    return dict(status="accepted", stripes=s, level_cm=cm, level_vs_guide_cm=rel, soil_state=state), max(acc) - min(acc) <= 1


if __name__ == "__main__":
    print(json.dumps(visit([measure(open(p, "rb").read()) for p in sys.argv[1:]]), indent=1))
