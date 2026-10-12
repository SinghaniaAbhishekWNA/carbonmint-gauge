"""v0: the company's detector (src/enhanced-detector.ts), rebuilt in Python from its written description
(2026-10-12). The TypeScript source was not available, so where the description gives no number the choice is
marked ASSUMED. Hue in degrees 0-360, saturation and value in percent 0-100 (the usual TypeScript rgbToHsv).
The magenta rule is taken literally: hue 140-175 degrees (see MAGENTA_HUE)."""
import numpy as np

RED_HUE, RED_S, RED_V = (20, 330), 35, 50
MAGENTA_HUE, MAG_S, MAG_V = (140, 175), 40, 50      # literal; in degrees this is green-cyan, not pink
ROW_FRAC = 0.20          # ASSUMED: "enough of the row is pink"
SPAN_FRAC = 0.28         # ASSUMED: "the pink spans enough of the column" (same 28% as the bar width rule)
MERGE_GAP, MIN_H, MIN_W, MIN_FILL, SOLID = 3, 5, 0.28, 0.45, 0.45
RUN_SPLIT, PITCH_SKIP, HOLE, PASSES = 4.5, 1.7, 1.65, 4
GUIDE_ZERO = 10
ACCEPT = 0.7
THICK_LIMIT = 2.5       # a bar up to 2.5x the expected 1 cm height scores as one stripe


def hsv(im):
    rgb = im.astype(np.float32) / 255
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.zeros_like(mx)
    nz = d > 1e-6
    rm = nz & (mx == r)
    gm = nz & (mx == g) & ~rm
    bm = nz & ~rm & ~gm
    h[rm] = (60 * ((g - b)[rm] / d[rm])) % 360
    h[gm] = 60 * ((b - r)[gm] / d[gm]) + 120
    h[bm] = 60 * ((r - g)[bm] / d[bm]) + 240
    s = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0) * 100
    return h, s, mx * 100


def pink_mask(im):
    h, s, v = hsv(im)
    R, G, B = im[..., 0].astype(int), im[..., 1].astype(int), im[..., 2].astype(int)
    red = ((h <= RED_HUE[0]) | (h >= RED_HUE[1])) & (s >= RED_S) & (v >= RED_V) & (R > G) & (R > B)
    mag = (h >= MAGENTA_HUE[0]) & (h <= MAGENTA_HUE[1]) & (s >= MAG_S) & (v >= MAG_V)
    return red | mag


def pitch_of(gaps):
    """Median neighbour gap; gaps already >= 1.7x the current pitch are left out, refined up to four passes."""
    p = float(np.median(gaps))
    for _ in range(PASSES):
        keep = gaps[gaps < PITCH_SKIP * p]
        if not len(keep):
            break
        q = float(np.median(keep))
        if q == p:
            break
        p = q
    return p


def read(im):
    """Returns dict(cm, level, state, confidence, stripes, hidden, column_x, accepted)."""
    H, W = im.shape[:2]
    pink = pink_mask(im)
    w = int(np.clip(round(0.02 * W), 36, 180))
    cols = np.concatenate([[0], np.cumsum(pink.sum(0))])
    x0 = int(np.argmax(cols[w:] - cols[:-w]))
    col = pink[:, x0:x0 + w]
    out = dict(cm=None, level=None, state=None, confidence=0.0, stripes=0, hidden=0, column_x=x0 + w // 2, accepted=False)
    if col.any(1).sum() < 0.02 * H:
        return out
    frac = col.mean(1)
    xs = np.arange(w)
    anyp = col.any(1)
    first = np.where(anyp, np.argmax(col, 1), 0)
    last = np.where(anyp, w - 1 - np.argmax(col[:, ::-1], 1), 0)
    span = np.where(anyp, last - first + 1, 0) / w
    rowon = (frac >= ROW_FRAC) & (span >= SPAN_FRAC)
    bars, start, gap = [], None, 0
    for y in range(H + 1):
        on = y < H and rowon[y]
        if on:
            if start is None:
                start = y
            gap, end = 0, y
        elif start is not None:
            gap += 1
            if gap > MERGE_GAP or y == H:
                bars.append((start, end + 1)); start, gap = None, 0
    kept = []
    for a, b in bars:
        blk = col[a:b]
        xs_on = np.nonzero(blk.any(0))[0]
        bw = (xs_on.max() - xs_on.min() + 1) if len(xs_on) else 0
        fill = blk[:, xs_on.min():xs_on.max() + 1].mean() if len(xs_on) else 0
        if b - a >= MIN_H and bw >= MIN_W * w and fill >= MIN_FILL:
            kept.append(dict(y0=a, y1=b, c=(a + b) / 2, bw=bw, solid=min(1.0, frac[a:b].max() / SOLID)))
    if not kept:
        return out
    # longest run of stripes whose gaps are on the gauge's scale
    if len(kept) > 1:
        g = np.diff([k["c"] for k in kept])
        tight = float(np.percentile(g, 25))           # ASSUMED: "typical tight spacing" = lower quartile gap
        runs, cur = [], [kept[0]]
        for k, gg in zip(kept[1:], g):
            if gg > RUN_SPLIT * tight:
                runs.append(cur); cur = []
            cur.append(k)
        runs.append(cur)
        kept = max(runs, key=len)
    n = len(kept)
    hidden = holes = 0
    spacing = 1.0
    if n > 1:
        g = np.diff([k["c"] for k in kept])
        p = pitch_of(g)
        hole = g >= HOLE * p
        for gg in g[hole]:
            hidden += int(round(gg / p)) - 1
            holes += 1
        vis = g[~hole]
        if len(vis) > 1 and vis.mean() > 0:
            spacing = max(0.3, 1 - float(vis.std() / vis.mean()))
    inferred = max(0.5, 1 - 0.1 * holes)
    solid = float(np.mean([k["solid"] for k in kept]))
    thick = float(np.mean([1.0 if (k["y1"] - k["y0"]) <= THICK_LIMIT * k["bw"] / 5 else 0.25 for k in kept]))
    conf = spacing * inferred * solid * thick
    cm = n + hidden
    level = cm - GUIDE_ZERO
    state = "Flooded" if level > 2 else "Saturated" if level >= -2 else "Drying" if level >= -12 else "Irrigate now"
    out.update(cm=cm, level=level, state=state, confidence=round(conf, 3), stripes=n, hidden=hidden,
               accepted=conf >= ACCEPT)
    return out
