"""P3.1.3 CLI: python -m gauge.read <photo> -> rings, pitch_px, cap_ratio, confidence."""
import json, sys
from .detect import load, detect
from .measure import read


def read_photo(path):
    im = load(path)
    det = detect(im)
    if det is None:
        return dict(rings=None, confidence=0.0, reason="no rod found")
    r = read(im, det)
    r["rod_center"] = [round(float(v)) for v in det["center"]]
    return r


if __name__ == "__main__":
    print(json.dumps(read_photo(sys.argv[1]), indent=1))
