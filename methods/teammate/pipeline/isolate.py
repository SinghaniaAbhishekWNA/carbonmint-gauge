"""P1.1 colour isolation â€” a 'pseudo-thermal' view from a normal RGB drone photo.

Vegetation (green/yellow hues) is pushed to zero; the gauge's own colours glow:
  red    â€” the ring markings (strongest cue)
  grey   â€” the PVC stem and cylinder body (low saturation, mid/high brightness)
  black  â€” the steel sleeve and lid (very dark, low saturation)

python pipeline/isolate.py            heat maps for all 128 photos -> results/isolate/
python pipeline/isolate.py --check    distance from each colour mask to the marked pipe point (10 clear photos)
"""
import csv, pathlib, sys, time
import cv2, numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORK_W = 1000  # processing width; full frames are 4096 px

# Colour thresholds in OpenCV HSV (H 0-179, S/V 0-255). ponytail: hand-tuned on this batch; re-tune per camera/season.
# Values sampled along the stem/sleeve of 9 photos: the PVC is a pale blue-grey (H 100-113, S 70-110),
# rings in shade go pink (H 150-178, S 50-95), the sleeve is very dark with a blue tint (V < 30, S up to 130).
RED_H_LO, RED_H_HI, RED_S, RED_V = 10, 154, 50, 60
VEG_H = (22, 95)            # yellow-green to green: rice, weeds, seed heads
PVC_H, PVC_S, PVC_V = (92, 128), 135, 70   # blue-grey PVC
GREY_S, GREY_V = 30, 110                   # neutral grey (sun-bleached PVC)
BLACK_V = 45
WEIGHTS = {"red": 1.0, "grey": 0.45, "black": 0.35}


def photos():
    """{idx: (path, class)} from the visibility CSV."""
    out = {}
    for r in csv.DictReader(open(ROOT / "sorted/visibility_labels.csv", encoding="utf-8")):
        i = int(r["idx"])
        out[i] = (ROOT / "sorted" / r["class"] / f'{i:03d}__{r["checkpoint_folder"].replace(" ", "_")}__{r["file"]}', r["class"])
    return out


def points():
    """{idx: (x, y)} hand-marked pipe points in full-resolution pixels."""
    return {int(r["idx"]): (int(r["x"]), int(r["y"])) for r in csv.DictReader(open(ROOT / "data/pipe_points.csv"))}


def load(path):
    im = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    scale = WORK_W / im.shape[1]
    return cv2.resize(im, (WORK_W, round(im.shape[0] * scale)), interpolation=cv2.INTER_AREA), scale


PREPROCESS = None  # set to normalize to apply colour constancy before thresholding (method 3)


def normalize(img):
    """Brightness constancy for method 3. Reconstructed from the outside literature (normalise illumination
    before HSV thresholds) and tested part by part on clear+partial:
      - gray-world white balance HURT (45/52 -> 23/52): in paddy photos the non-green pixels are mostly brown
        soil, so 'make them gray' pulls the red out of the rings. Dropped.
      - brightness gain HELPED (45 -> 49/52; dark-photo attack 39 -> 45/52). Kept: scale so the 90th
        luminance percentile sits at a fixed level."""
    f = img.astype(np.float32)
    f *= np.clip(190.0 / max(np.percentile(f.mean(axis=2), 90), 1), 0.7, 1.6)
    return np.clip(f, 0, 255).astype(np.uint8)


def isolate(img):
    """Return per-colour boolean masks and a 0-255 'heat' image."""
    if PREPROCESS is not None:
        img = PREPROCESS(img)
    h, s, v = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2HSV))
    veg = (h >= VEG_H[0]) & (h <= VEG_H[1]) & (s > 50)
    red = ((h < RED_H_LO) | (h > RED_H_HI)) & (s > RED_S) & (v > RED_V)
    grey = (((h >= PVC_H[0]) & (h <= PVC_H[1]) & (s <= PVC_S) & (v >= PVC_V)) | ((s < GREY_S) & (v >= GREY_V))) & ~veg
    black = (v < BLACK_V) & ~veg
    k = np.ones((3, 3), np.uint8)
    masks = {n: cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, k).astype(bool)
             for n, m in (("red", red), ("grey", grey), ("black", black))}
    heat = sum(WEIGHTS[n] * masks[n].astype(np.float32) for n in masks)
    heat = cv2.GaussianBlur(heat, (0, 0), 3)
    heat[veg] *= 0.2
    heat = np.clip(heat / max(heat.max(), 1e-6) * 255, 0, 255).astype(np.uint8)
    return masks, heat


def render(img, masks, heat):
    vis = cv2.applyColorMap(heat, cv2.COLORMAP_INFERNO)
    m = np.zeros_like(img)
    m[masks["black"]] = (255, 80, 0)
    m[masks["grey"]] = (200, 200, 200)
    m[masks["red"]] = (0, 0, 255)
    return np.hstack([img, vis, m])


def check():
    ph, pt = photos(), points()
    clear = [i for i in sorted(ph) if ph[i][1] == "1_clear"][::6][:10]
    ok, tiles = True, []
    print("idx      red     grey    black   (density on the gauge column / density over the whole photo; >= 3 = concentrated)")
    for i in clear:
        img, sc = load(ph[i][0])
        masks, _ = isolate(img)
        px, py = pt[i][0] * sc, pt[i][1] * sc
        H, W = masks["red"].shape
        x0, x1 = max(int(px - 80 * sc), 0), int(px + 80 * sc) + 1
        y0, y1 = max(int(py - 1500 * sc), 0), min(int(py + 400 * sc), H)
        lift = []
        for n in ("red", "grey", "black"):
            m = masks[n]
            whole = m.mean()
            lift.append(m[y0:y1, x0:x1].mean() / whole if whole else 0.0)
        hit = all(x >= 3 for x in lift)
        ok &= hit
        print(f"{i:3d}  " + "  ".join(f"{x:7.1f}" for x in lift) + ("   ok" if hit else "   MISS (a colour is not concentrated on the gauge)"))
        t = render(img, masks, isolate(img)[1])[:, W:]  # heat | masks, with the gauge column drawn
        for off in (0, W):
            cv2.rectangle(t, (x0 + off, y0), (x1 + off, y1), (0, 255, 0) if hit else (0, 0, 255), 2)
        cv2.putText(t, f"{i}  red {lift[0]:.0f}x grey {lift[1]:.0f}x black {lift[2]:.1f}x", (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        tiles.append(cv2.resize(t, (1000, round(t.shape[0] * 1000 / t.shape[1]))))
    cv2.imwrite(str(ROOT / "results/isolate_check.jpg"), np.vstack([np.hstack(tiles[k:k + 2]) for k in range(0, len(tiles), 2)]))
    print("RESULT", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def main():
    out = ROOT / "results/isolate"
    out.mkdir(parents=True, exist_ok=True)
    t = time.time()
    ph = photos()
    for i, (p, cls) in sorted(ph.items()):
        img, _ = load(p)
        masks, heat = isolate(img)
        cv2.imwrite(str(out / f"{i:03d}_{cls}.jpg"), render(img, masks, heat), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"{len(ph)} photos -> {out} in {time.time() - t:.1f}s")
    # sample montage for the evidence screenshot: clear, partial and hard examples
    picks = [22, 68, 89, 1, 57, 108, 112, 126]
    tiles = [cv2.resize(cv2.imread(str(next(out.glob(f"{i:03d}_*.jpg")))), (1500, 375)) for i in picks]
    cv2.imwrite(str(ROOT / "results/isolate_montage.jpg"), np.vstack(tiles))
    n = len(list(out.glob("*.jpg")))
    print(f"files written: {n}  (photo | pseudo-thermal heat | colour masks: red=rings, grey=PVC, blue=black sleeve)")
    print("RESULT", "PASS" if n == len(ph) and time.time() - t < 180 else "FAIL")


if __name__ == "__main__":
    check() if "--check" in sys.argv else main()
