"""P3 Measure, don't count. Straighten the rod, find the ring rhythm (pitch), the first ring, the sleeve edge and the
rod top; reading = rings between the first ring and the sleeve, so rings hidden by leaves still count."""
import numpy as np
from scipy import ndimage as ndi
from scipy.signal import find_peaks
from .detect import ring_mask, grey_mask


def sample(im, c, d, T, S):
    n = np.array([-d[1], d[0]])
    px = c[0] + T[:, None] * d[0] + S[None, :] * n[0]
    py = c[1] + T[:, None] * d[1] + S[None, :] * n[1]
    return np.stack([ndi.map_coordinates(im[..., k].astype(float), [py, px], order=1, mode="nearest")
                     for k in range(3)], -1).astype(np.int16)


def straighten(im, det, up, down):
    """Rod core as a straight strip. A wide first pass finds the ring centre per row; a quadratic through those
    centres follows tilt errors and gently bent rods. Returns (core strip, image-y per row)."""
    c, d, h = det["center"], det["dir"], det["half"]
    T = np.arange(det["t0"] - up, det["t1"] + down)
    S = np.arange(-2.5 * h, 2.5 * h + 1)
    wide = sample(im, c, d, T, S)
    red = ring_mask(wide)
    cnt = red.sum(1)
    rows = np.nonzero(cnt >= max(2, 0.2 * h))[0]
    if len(rows) >= 10:
        cen = (red * S[None, :]).sum(1)[rows] / cnt[rows]
        fit = np.polyfit(rows, cen, 2 if len(rows) > 60 else 1)
        off = np.polyval(fit, np.arange(len(T)))
        lo, hi = rows.min(), rows.max()                       # hold the offset flat outside the ring span
        off[:lo], off[hi + 1:] = off[lo], off[hi]
    else:
        off = np.zeros(len(T))
    W = np.arange(-0.6 * h, 0.6 * h + 1)
    cols = (off[:, None] + W[None, :] - S[0])                # column index into the wide strip
    rr = np.repeat(np.arange(len(T))[:, None], len(W), 1)
    core = np.stack([ndi.map_coordinates(wide[..., k].astype(float), [rr, cols], order=1, mode="nearest")
                     for k in range(3)], -1).astype(np.int16)
    n = np.array([-d[1], d[0]])
    return core, c[1] + T * d[1] + off * n[1]


def pitch(sig, lo=6, hi=160):
    """Ring pitch in px from the autocorrelation of the redness wave (sub-pixel, parabolic)."""
    x = sig - sig.mean()
    hi = min(hi, len(x) // 2)
    if hi <= lo + 2 or not x.any():
        return None, 0.0
    ac = np.correlate(x, x, "full")[len(x) - 1:]
    ac = ac / ac[0]
    pk, _ = find_peaks(ac[:hi])
    pk = pk[pk >= lo]
    if not len(pk):
        return None, 0.0
    m = ac[pk].max()
    k = pk[ac[pk] >= 0.75 * m][0] if m > 0 else pk[np.argmax(ac[pk])]   # shortest strong lag: the strongest can be
                                                                        # 2-4x the true gap; no positive peak: strongest
    y0, y1, y2 = ac[k - 1], ac[k], ac[k + 1]
    den = y0 - 2 * y1 + y2
    return float(k + (0.5 * (y0 - y2) / den if den else 0)), float(ac[k])


def rod_run(rod, seed, gap):
    """Rows [a, b] of the rod around `seed`: rod-coloured rows, bridging occlusions shorter than `gap` rows."""
    a = b = seed
    miss = 0
    while b + 1 < len(rod) and miss <= gap:
        b += 1
        miss = 0 if rod[b] else miss + 1
    b -= miss
    miss = 0
    while a > 0 and miss <= gap:
        a -= 1
        miss = 0 if rod[a] else miss + 1
    return a + miss, b


def read(im, det):
    """Reading for one detected rod: dict(rings, pitch_px, first_y, last_y, sleeve_y, top_y, cap_ratio, confidence)."""
    L = det["t1"] - det["t0"]
    up, down = 0.6 * L + 80, 0.5 * L + 150
    core, ys = straighten(im, det, up, down)
    redf = ring_mask(core).mean(1)
    greyf = grey_mask(core).mean(1)
    r, g, b = core[..., 0], core[..., 1], core[..., 2]
    redness = np.clip(np.median(r - np.maximum(g, b), 1), 0, None)
    gray = core.astype(np.float32).mean(-1)
    sharp = float(np.abs(np.diff(gray, 2, axis=0)).mean())    # rod-core detail along the axis: blur lowers it
    out = dict(rings=0.0, pitch_px=None, first_y=None, last_y=None, sleeve_y=None, top_y=None, cap_ratio=None,
               confidence=0.0, rod_len_px=round(L), strength=0.0, seen=0.0, peaks=0, sharp=round(sharp, 2),
               ringfrac=round(float((redf > 0.15).mean()), 3))
    ringrow = redf > 0.15
    if ringrow.sum() < 4:                                   # no paint showing: an all-grey rod reads 0 rings
        out["confidence"] = 0.6 if L > 6 * det["half"] else 0.3
        return out
    rows = np.nonzero(ringrow)[0]
    p, strength = pitch(redness[rows.min(): rows.max() + 1])
    pk0, _ = find_peaks(np.where(ringrow, redness, 0), distance=max(3, int(0.3 * det["half"])), prominence=10)
    if 2 <= len(pk0) <= 6:                                  # few rings: their spacing beats the autocorrelation
        p, strength = float(np.median(np.diff(pk0))), max(strength, 0.5)
    if p is None or p < 4:
        p, strength = 2.5 * det["half"], 0.2
    # the rod: rod-coloured rows around the ring mass, bridging leaves up to ~3 pitches
    rodrow = (redf + greyf) > 0.3
    seed = int(np.median(rows))
    a, s = rod_run(rodrow, seed, int(4 * p))
    pk, _ = find_peaks(np.where(ringrow, redness, 0), distance=max(3, int(0.6 * p)))
    pk = pk[(pk >= a) & (pk <= s)]
    if not len(pk):
        out["confidence"] = 0.2
        return out
    # a faint band at either end is a sleeve rim or a stain, not a ring: real rings are strongly saturated
    if len(pk) >= 3:
        strong = 0.3 * np.median(redness[pk])
        while len(pk) >= 3 and redness[pk[-1]] < strong:
            pk = pk[:-1]
        while len(pk) >= 3 and redness[pk[0]] < strong:
            pk = pk[1:]
    first, last = pk.min(), pk.max()
    n = round((last - first) / p) + 1
    if len(pk) >= 3:                                      # perspective changes the gap along the rod: count gap by
        g = np.diff(pk).astype(float)                     # gap against the local pitch, not one global pitch
        n = 1
        for i, gi in enumerate(g):
            near = g[max(0, i - 4): i + 5]
            near = near[(near > 0.6 * p) & (near < 1.5 * p)]
            q = gi / (np.median(near) if len(near) else p)
            n += max(1, round(q))
    # ponytail: rings hidden right at the sleeve are not added back (sleeve colour varies by plot); the
    # timeline and two-shot fusion catch those cases instead.
    s = min(s, last + int(p / 2))
    t = max(a, first - int(0.4 * p))                      # top: walk up from above the first ring while still PVC
    while t > a and greyf[max(a, t - 3):t].mean() > 0.2:
        t -= 1
    seen = len(pk) / max(n, 1)
    out.update(strength=round(float(strength), 3), seen=round(float(seen), 3), peaks=int(len(pk)))
    out.update(rings=float(n), pitch_px=round(p, 1), first_y=round(float(ys[first])), last_y=round(float(ys[last])),
               sleeve_y=round(float(ys[s])), top_y=round(float(ys[t])), cap_ratio=round((first - t) / p, 2),
               confidence=round(float(np.clip(strength, 0, 1) * min(1.0, seen) * min(1.0, p / 12)), 2))
    return out
