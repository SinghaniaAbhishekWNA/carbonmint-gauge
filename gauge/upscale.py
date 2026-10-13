"""Upscayl (upscayl-bin, model upscayl-standard-4x) on gauge crops, with the pre-registered triggers and adoption
rules of docs/upscale_check.md. Off unless UPSCALE=on; any engine failure leaves the photo's normal reading in place.
Never upscales a whole photo: only a crop around the gauge."""
import hashlib, os, shutil, subprocess, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
from .detect import detect
from .measure import read

REPO = Path(__file__).resolve().parents[1]
UP = REPO / "third_party" / "upscayl"
BIN = Path(os.environ.get("UPSCAYL_BIN", UP / "bin" / ("upscayl-bin.exe" if os.name == "nt" else "upscayl-bin")))
MODELS = Path(os.environ.get("UPSCAYL_MODELS", UP / "models"))
MODEL = os.environ.get("UPSCAYL_MODEL", "upscayl-standard-4x")
SCALE = 4
CACHE = Path(os.environ.get("UPSCAYL_CACHE", REPO / "data" / "cache" / "upscayl"))
THIN_HALF, FINE_PITCH = 14, 16          # pre-registered triggers (docs/upscale_check.md)


def enabled():
    return os.environ.get("UPSCALE", "off").lower() == "on"


def triggers(row):
    """Why this photo's gauge should be upscaled, from its normal v1 read (empty list = leave it alone)."""
    f = lambda k: float(row[k]) if row.get(k) not in ("", None) else None
    if row.get("rings") in ("", None):
        return ["no rod"]
    if f("half") is not None and f("half") < THIN_HALF:
        return ["thin rod"]
    if f("pitch_px") is not None and 0 < f("pitch_px") < FINE_PITCH:
        return ["fine pitch"]
    return []


def crop_for_rod(row, shape):
    """(x0, y0, x1, y1) around the rod the normal read found: the stretch the reader samples, +-(4 half-widths + 32)."""
    f = lambda k: float(row[k])
    c, d, h = np.array([f("cx"), f("cy")]), np.array([f("dx"), f("dy")]), f("half")
    L = f("t1") - f("t0")
    ends = [c + d * (f("t0") - 0.6 * L - 80), c + d * (f("t1") + 0.5 * L + 150)]
    pad = 4 * h + 32
    return _clip(min(e[0] for e in ends) - pad, min(e[1] for e in ends), max(e[0] for e in ends) + pad,
                 max(e[1] for e in ends), shape)


def crop_for_box(box, shape):
    """Around a colour-locator box: half its width either side, a quarter of its height above and below."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    return _clip(x0 - w / 2, y0 - h / 4, x1 + w / 2, y1 + h / 4, shape)


def _clip(x0, y0, x1, y1, shape):
    H, W = shape[:2]
    return int(max(0, x0)), int(max(0, y0)), int(min(W, x1)), int(min(H, y1))


def _key(crop):
    return hashlib.sha1(crop.tobytes() + str(crop.shape).encode() + MODEL.encode()).hexdigest()


def upscale_many(crops, timeout=3600):
    """Upscale RGB uint8 crops x4 with one upscayl-bin call. Cached by crop content. Failures give None."""
    out, todo = [None] * len(crops), []
    CACHE.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(crops):
        f = CACHE / f"{_key(c)}.png"
        if f.exists():
            out[i] = np.asarray(Image.open(f).convert("RGB"))
        else:
            todo.append(i)
    if not todo or not BIN.exists():
        return out
    tmp = Path(tempfile.mkdtemp(prefix="upscayl-"))
    try:
        (tmp / "in").mkdir(); (tmp / "out").mkdir()
        for i in todo:
            Image.fromarray(crops[i]).save(tmp / "in" / f"{i:05d}.png")
        subprocess.run([str(BIN), "-i", str(tmp / "in"), "-o", str(tmp / "out"), "-s", str(SCALE), "-m", str(MODELS),
                        "-n", MODEL, "-f", "png"], check=True, capture_output=True, timeout=timeout)
        for i in todo:
            f = tmp / "out" / f"{i:05d}.png"
            if f.exists():
                up = np.asarray(Image.open(f).convert("RGB"))
                if up.shape[:2] == (crops[i].shape[0] * SCALE, crops[i].shape[1] * SCALE):
                    out[i] = up
                    shutil.copyfile(f, CACHE / f"{_key(crops[i])}.png")
    except (subprocess.SubprocessError, OSError):
        pass                                             # engine missing or failed: those crops stay None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def read_upscaled(up, x0, y0):
    """v1's own finder and reader on an upscaled crop, mapped back to photo coordinates. None if no rod."""
    det = detect(up.astype(np.int16))
    if det is None:
        return None
    r = read(up.astype(np.int16), det)
    s = float(SCALE)
    row = {k: ("" if v is None else v) for k, v in r.items()}
    for k in ("first_y", "last_y", "sleeve_y", "top_y"):
        if row[k] != "":
            row[k] = round(y0 + row[k] / s)
    for k in ("pitch_px", "rod_len_px"):
        if row[k] != "":
            row[k] = round(row[k] / s, 1)
    row.update(cx=round(x0 + det["center"][0] / s, 1), cy=round(y0 + det["center"][1] / s, 1), half=round(det["half"] / s, 1),
               dx=round(det["dir"][0], 4), dy=round(det["dir"][1], 4), t0=round(det["t0"] / s, 1), t1=round(det["t1"] / s, 1))
    return row


def adopt(orig_rings, up_row, twin_rings):
    """Pre-registered rules R1-R3. Returns (adopt?, rule that decided)."""
    if up_row is None or up_row.get("rings") in ("", None):
        return False, "R1: upscaled crop gave no reading"
    n = float(up_row["rings"])
    o = None if orig_rings in ("", None) else float(orig_rings)
    t = None if twin_rings in ("", None) else float(twin_rings)
    if o == 0 and n > 0 and not (t is not None and t > 0):
        return False, "R2: would turn a dry reading into stripes; other shot does not show stripes"
    if t is not None and abs(n - t) > 1:
        return False, f"R3: upscaled {n:g} disagrees with the other shot ({t:g})"
    return True, "adopted" + (f": agrees with the other shot ({t:g})" if t is not None else ": no other shot")
