"""v1: our reader + a trained confidence model + the company's acceptance rule.

Reader: gauge.detect + gauge.measure (straighten the rod, read the ring rhythm; hidden rings counted).
Confidence: a small logistic model that predicts P(reading is exactly right) from the reader's own signals and
whether the visit's other shot agrees. A photo is accepted when that probability is >= 0.7 (the company's bar),
so 0.7 keeps its meaning: "probably exact". A folder (visit) takes the mean of its accepted photos.
Bad gauge: a reading that breaks the gauge's physics (more rings than the scale holds, or a ring spacing that
does not fit the rod's width) is never accepted and carries the note "bad gauge"."""
import json
import numpy as np

ACCEPT = 0.7
SCALE_MAX = 25            # most rings seen on a fully raised stem in the pilot photos
PITCH_PER_HALF = (0.45, 1.7)   # ring spacing / rod half-width; correct pilot readings span 0.64-1.18 (n=62)
FEATURES = ["confidence", "strength", "seen", "logsharp", "logrod", "ringfrac", "sib_same", "sib_near", "sib_none", "zero"]


def bad_gauge(r):
    """Physics check on one photo's reading. Returns a note or ''."""
    if r.get("rings") in ("", None):
        return ""
    n = float(r["rings"])
    if n > SCALE_MAX:
        return f"bad gauge: {n:.0f} rings is more than the scale holds"
    if n >= 3 and r.get("pitch_px") not in ("", None) and r.get("half") not in ("", None):
        k = float(r["pitch_px"]) / max(float(r["half"]), 1e-6)
        if not PITCH_PER_HALF[0] <= k <= PITCH_PER_HALF[1]:
            return "bad gauge: ring spacing does not fit the rod width"
    return ""


def fallback(r, teammate):
    """When our rod finder sees nothing, use the teammate's colour locator (methods/teammate, method 3 final): if it
    finds the gauge, take its ring count. Its own score is not trusted, so the reading enters at low confidence and
    the model decides. Local lane only: it needs the teammate run (OpenCV) on the visit's photos."""
    if r.get("rings") not in ("", None) or teammate.get("state") in (None, "unreadable"):
        return r
    return dict(r, rings=float(teammate.get("rings") or 0), confidence=0.3, source="teammate locator")


def features(r, sibling_rings):
    """Feature vector for one photo. sibling_rings: readings of the visit's other shots (may be empty)."""
    f = lambda k: float(r[k]) if r.get(k) not in ("", None) else 0.0
    n = r.get("rings")
    sibs = [float(s) for s in sibling_rings if s not in ("", None)]
    if n in ("", None):
        same = near = 0.0
    else:
        same = float(any(s == float(n) for s in sibs))
        near = float(any(abs(s - float(n)) <= 1 for s in sibs))
    return np.array([f("confidence"), f("strength"), f("seen"), np.log1p(f("sharp")), np.log1p(f("rod_len_px")),
                     f("ringfrac"), same, near, float(not sibs), float(n not in ("", None) and float(n) == 0)])


class Model:
    """Logistic regression with L2, fitted by Newton steps (numpy only)."""

    def __init__(self, l2=1.0):
        self.l2, self.w, self.mu, self.sd = l2, None, None, None

    def fit(self, X, y):
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-6
        Z = np.c_[np.ones(len(X)), (X - self.mu) / self.sd]
        w = np.zeros(Z.shape[1])
        reg = np.eye(len(w)) * self.l2; reg[0, 0] = 0
        for _ in range(50):
            p = 1 / (1 + np.exp(-Z @ w))
            g = Z.T @ (p - y) + reg @ w
            Hm = Z.T @ (Z * (p * (1 - p))[:, None]) + reg
            step = np.linalg.solve(Hm, g)
            w -= step
            if np.abs(step).max() < 1e-8:
                break
        self.w = w
        return self

    def prob(self, X):
        Z = np.c_[np.ones(len(X)), (X - self.mu) / self.sd]
        return 1 / (1 + np.exp(-Z @ self.w))

    def to_json(self):
        return json.dumps(dict(features=FEATURES, w=self.w.tolist(), mu=self.mu.tolist(), sd=self.sd.tolist(), l2=self.l2))

    @classmethod
    def from_json(cls, s):
        d = json.loads(s)
        m = cls(d["l2"]); m.w, m.mu, m.sd = np.array(d["w"]), np.array(d["mu"]), np.array(d["sd"])
        return m


GUIDE_ZERO = 10          # company spec: the guide zero sits 10 cm along the counted stripes (1 stripe = 1 cm)


def soil(cm):
    """Company spec: level relative to the guide -> soil state."""
    if cm is None:
        return None, None
    level = cm - GUIDE_ZERO
    return level, ("Flooded" if level > 2 else "Saturated" if level >= -2 else "Drying" if level >= -12 else "Irrigate now")


def decide(r, p):
    """Final v1 outcome for one photo given its reading row and model probability."""
    note = bad_gauge(r)
    has = r.get("rings") not in ("", None)
    if not has:
        return dict(cm=None, confidence=0.0, accepted=False, note="no gauge found", level=None, state=None)
    if note:
        out = dict(cm=float(r["rings"]), confidence=round(min(float(p), ACCEPT - 0.01), 3), accepted=False, note=note)
    else:
        out = dict(cm=float(r["rings"]), confidence=round(float(p), 3), accepted=bool(p >= ACCEPT),
                   note="" if p >= ACCEPT else "review: confidence below 0.7")
    out["level"], out["state"] = soil(out["cm"])
    return out


def folder(photos):
    """Company folder rule: mean of accepted photos; none accepted -> stays in review."""
    acc = [d["cm"] for d in photos if d["accepted"]]
    return dict(cm=round(sum(acc) / len(acc), 1) if acc else None, state="accepted" if acc else "review")
