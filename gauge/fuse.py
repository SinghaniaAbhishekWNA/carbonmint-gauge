"""P4 Fuse and sanity-check: two shots -> one visit reading; per-plot timeline spike check; review rule."""


def fuse(shots, agree=1.0, min_conf=0.3):
    """shots: list of dict(rings: float|None, confidence: float). Returns dict(rings, confidence, flags)."""
    ok = [s for s in shots if s.get("rings") is not None]
    if not ok:
        return dict(rings=None, confidence=0.0, flags=["no rod found"])
    best = max(ok, key=lambda s: s["confidence"])
    sure = [s for s in ok if s["confidence"] >= min_conf] or [best]
    vals = [s["rings"] for s in sure]
    flags = []
    if max(vals) - min(vals) > agree:
        flags.append("shots disagree")
        rings = best["rings"]
    else:
        w = sum(s["confidence"] for s in sure) or 1.0
        rings = round(2 * sum(s["rings"] * s["confidence"] for s in sure) / w) / 2 if w else best["rings"]
    return dict(rings=rings, confidence=best["confidence"], flags=flags)


def timeline(series, jump=4.0, calm=3.0):
    """series: readings in date order (None allowed). A reading is flagged when it differs from both neighbours by
    more than `jump` rings while the neighbours agree within `calm`: a one-day spike no field does. Returns flags."""
    flags = [False] * len(series)
    idx = [i for i, v in enumerate(series) if v is not None]
    for a, b, c in zip(idx, idx[1:], idx[2:]):
        pa, pb, pc = series[a], series[b], series[c]
        if abs(pa - pc) <= calm and abs(pb - pa) > jump and abs(pb - pc) > jump:
            flags[b] = True
    return flags


def smooth(series):
    """Median of 3 over the non-missing readings (endpoints kept)."""
    idx = [i for i, v in enumerate(series) if v is not None]
    out = list(series)
    for a, b, c in zip(idx, idx[1:], idx[2:]):
        out[b] = sorted([series[a], series[b], series[c]])[1]
    return out


def accept(confidence, flags, tau):
    """Review-queue rule: auto-accept only a confident reading with no flags; everything else goes to a person."""
    return confidence >= tau and not flags
