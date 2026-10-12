"""P2.1.1 Classic colour detector. The rod is blue-grey PVC with red rings; rice, weeds and soil are
green or brown, so blue-grey + red pixels in a tall thin cluster locate the rod even with zero rings showing."""
import numpy as np
from PIL import Image
from scipy import ndimage as ndi


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.int16)


def red_mask(im, lo=60):
    R, G, B = im[..., 0], im[..., 1], im[..., 2]
    M = np.maximum(G, B)
    # relative test so rings in shade (R~64, G~10) count too; straw is yellow (G >> B), rings are not
    return (R - M > lo * R / 160) & (R > 1.6 * M + 10) & (R > 40) & (np.abs(G - B) < 30)


def grey_mask(im):
    R, G, B = im[..., 0], im[..., 1], im[..., 2]
    return (B >= G - 10) & (B - R > 5) & (B > 45) & (B - G < 60)   # blue-grey PVC, sun or shade


def detect(im):
    c = candidates(im)
    return c[0] if c else None


def ring_mask(im):
    """Red or washed-out pink ring paint. Straw (G >> B) and brown soil (G > B) are excluded."""
    R, G, B = im[..., 0], im[..., 1], im[..., 2]
    M = np.maximum(G, B)
    return (R - M > 25) & (R > 1.25 * M) & (R > 40) & (B >= G - 12)


def _axis(xs, ys):
    c = np.array([xs.mean(), ys.mean()])
    _, s, vt = np.linalg.svd(np.stack([xs - c[0], ys - c[1]], 1), full_matrices=False)
    d = vt[0] if vt[0][1] > 0 else -vt[0]
    t = (xs - c[0]) * d[0] + (ys - c[1]) * d[1]
    w = np.abs((xs - c[0]) * -d[1] + (ys - c[1]) * d[0])
    return c, d, s, t, w


def ring_stacks(im):
    """Stacks of >= 3 separate ring blobs along a near-vertical line: the rod with rings showing.
    Pieces of one rod split by a leaf are merged when they lie on the same axis."""
    red = ring_mask(im)
    blobs, nb = ndi.label(red)
    if nb == 0:
        return []
    size = ndi.sum(red, blobs, range(1, nb + 1))
    keep = np.isin(blobs, 1 + np.nonzero(size >= 8)[0])
    tall = ndi.maximum_filter1d(ndi.maximum_filter1d(keep.view(np.uint8), 71, 0), 3, 1)
    groups, ng = ndi.label(tall)
    pts = lookup(groups, keep)
    pieces = []
    for gi in 1 + np.nonzero(ndi.sum(keep, groups, range(1, ng + 1)) >= 20)[0]:
        ys, xs = pts(gi)
        pieces.append((xs, ys))
    found = []
    while pieces:
        pieces.sort(key=lambda q: -len(q[0]))
        xs, ys = pieces.pop(0)
        c, d, s, t, w = _axis(xs, ys)
        if len(xs) >= 40 and abs(d[1]) >= 0.85:
            half = float(np.percentile(w, 95)) + 1
            L = t.max() - t.min()
            rest = []
            for qx, qy in pieces:                              # absorb pieces on this rod's axis
                qc = np.array([qx.mean(), qy.mean()])
                along = (qc - c) @ d
                off = abs((qc - c) @ np.array([-d[1], d[0]]))
                if off < 2.5 * half and abs(along) < L / 2 + 0.8 * L + 150:
                    xs, ys = np.concatenate([xs, qx]), np.concatenate([ys, qy])
                else:
                    rest.append((qx, qy))
            pieces = rest
            c, d, s, t, w = _axis(xs, ys)
        nring = len(np.unique(blobs[ys, xs]))
        if nring < 3 or abs(d[1]) < 0.85 or s[0] < 1.1 * s[1]:
            continue
        found.append(dict(score=len(ys) * min(nring, 30), center=c, dir=d, half=float(np.percentile(w, 95)) + 1,
                          t0=float(t.min()), t1=float(t.max()), red_px=len(ys), grey_px=0, rings_seen=nring))
    return sorted(found, key=lambda f: -f["score"])


def candidates(im):
    stacks = ring_stacks(im)
    if stacks:
        return stacks
    return grey_rods(im)


def grey_rods(im):
    """Rod candidates, best first. Each as dict(center, dir, half, t0, t1, red_px, grey_px) or None.
    dir is a unit vector pointing down the rod; t0/t1 bound the rod pixels along dir."""
    red, grey = red_mask(im, 40), grey_mask(im)
    rod = red | grey
    tall = ndi.maximum_filter1d(ndi.maximum_filter1d(rod.view(np.uint8), 121, 0), 5, 1)   # separable = fast
    groups, ng = ndi.label(tall)
    if ng == 0:
        return []
    sizes = ndi.sum(rod, groups, range(1, ng + 1))
    found = []
    pts = lookup(groups, rod)
    for gi in 1 + np.nonzero(sizes >= 150)[0]:
        ys, xs = pts(gi)
        c = np.array([xs.mean(), ys.mean()])
        _, s, vt = np.linalg.svd(np.stack([xs - c[0], ys - c[1]], 1), full_matrices=False)
        d = vt[0] if vt[0][1] > 0 else -vt[0]
        if abs(d[1]) < 0.85 or s[0] < 2.0 * s[1]:       # tall, thin, near-vertical
            continue
        t = (xs - c[0]) * d[0] + (ys - c[1]) * d[1]
        w = np.abs((xs - c[0]) * -d[1] + (ys - c[1]) * d[0])
        half = float(np.percentile(w, 90)) + 1
        L = float(t.max() - t.min())
        if L < 3 * half:
            continue
        nred = int(red[ys, xs].sum())
        fill = len(ys) / (L * 2 * half)
        if fill < 0.3:                   # solid tube, not scattered glints on a wet sleeve
            continue
        if len(ys) - nred < 0.15 * len(ys):              # a rod always shows some blue-grey PVC
            continue
        score = len(ys) * fill * (1 + min(nred / len(ys), 0.5) * 4)    # red rings make a candidate far more likely
        found.append(dict(score=score, center=c, dir=d, half=half, t0=float(t.min()), t1=float(t.max()), red_px=nred, grey_px=len(ys) - nred))
    return sorted(found, key=lambda f: -f["score"])


def lookup(groups, mask):
    """Fast per-group pixel lists: returns f(gi) -> (ys, xs) of mask pixels in group gi."""
    ys, xs = np.nonzero(mask & (groups > 0))
    g = groups[ys, xs]
    order = np.argsort(g, kind="stable")
    ys, xs, g = ys[order], xs[order], g[order]
    return lambda gi: (ys[np.searchsorted(g, gi):np.searchsorted(g, gi, "right")],
                       xs[np.searchsorted(g, gi):np.searchsorted(g, gi, "right")])


def box(det, pad=None):
    """Corner points of the oriented detection box around the rod pixels, padded along and across the rod."""
    L = det["t1"] - det["t0"]
    pad = 0.1 * L + 10 if pad is None else pad
    c, d = det["center"], det["dir"]
    n = np.array([-d[1], d[0]])
    hw = det["half"] * 1.6 + 6
    pts = [c + d * t + n * s for t in (det["t0"] - pad, det["t1"] + pad) for s in (-hw, hw)]
    return np.array([pts[0], pts[1], pts[3], pts[2]])


def inside(poly, p):
    """Point-in-convex-quad test."""
    sign = None
    for a, b in zip(poly, np.roll(poly, -1, 0)):
        cr = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        if sign is None:
            sign = cr > 0
        elif (cr > 0) != sign:
            return False
    return True
