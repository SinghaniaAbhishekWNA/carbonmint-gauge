"""python -m unittest tests/test_gauge.py  (-k Detect | Edges | Pitch | Read | Fuse | Timeline)
Synthetic rods with known answers, plus checks against the silver labels where data/ exists."""
import csv, os, sys, unittest
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gauge.detect import detect, box, inside
from gauge.measure import read, pitch
from gauge.fuse import fuse, timeline

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rod(rings=14, p=40, x=600, top=300, cap=3.0, width=50, leaves=(), sleeve="black", size=(1500, 1200), tilt=0.0):
    """Synthetic field photo: green background, blue-grey PVC rod, red rings every p px, leaves painting over
    the given ring indices, a dark (or grey) sleeve below the last ring. Returns (image, first ring y, sleeve y)."""
    H, W = size
    im = np.zeros((H, W, 3), np.int16); im[...] = (40, 90, 30)
    first = int(top + cap * p)
    sl = int(first + (rings - 0.5) * p)
    for y in range(top, H):
        cx = int(x + tilt * (y - top))
        if y < sl:
            im[y, cx - width // 2: cx + width // 2] = (80, 105, 130)
            k = (y - first + p // 4) // p
            if y >= first - p // 4 and (y - first + p // 4) % p < p // 2.5 and k < rings and k not in leaves:
                im[y, cx - width // 2: cx + width // 2] = (170, 20, 25)
        else:
            im[y, cx - width: cx + width] = (25, 25, 28) if sleeve == "black" else (90, 110, 125)
    return im, first, sl


class TestDetect(unittest.TestCase):
    def test_synthetic_box_contains_first_ring(self):
        im, first, _ = rod()
        det = detect(im)
        self.assertIsNotNone(det)
        self.assertTrue(inside(box(det), (600, first)))

    def test_labelled_photos(self):
        """On the real photos the box holds the first labelled ring in >= 90% of photos that show rings."""
        f = os.path.join(HERE, "data", "photo_reads.csv")
        if not os.path.exists(f):
            self.skipTest("run python -m gauge.run first")
        lab = {r["photo"]: r for r in csv.DictReader(open(os.path.join(HERE, "data", "labels.csv")))}
        n = hit = 0
        for r in csv.DictReader(open(f)):
            y = lab[r["photo"]]["first_ring_y"]
            if not y:
                continue
            n += 1
            if r["cx"] == "":
                continue
            det = dict(center=np.array([float(r["cx"]), float(r["cy"])]), dir=np.array([float(r["dx"]), float(r["dy"])]),
                       half=float(r["half"]), t0=float(r["t0"]), t1=float(r["t1"]))
            y = float(y)
            x = det["center"][0] + (y - det["center"][1]) / det["dir"][1] * det["dir"][0]
            hit += inside(box(det), (x, y))
        print(f"\n  detector box holds the first labelled ring in {hit}/{n} photos")
        self.assertGreaterEqual(hit / n, 0.9)


class TestEdges(unittest.TestCase):
    def test_synthetic_ends(self):
        im, first, sl = rod(rings=12, p=40)
        r = read(im, detect(im))
        self.assertLess(abs(r["first_y"] - first), 0.5 * 40)
        self.assertLess(abs(r["sleeve_y"] - sl), 0.5 * 40)
        self.assertLess(abs(r["top_y"] - 300), 0.5 * 40)

    def test_labelled_photos(self):
        """Median error of the first and last ring vs the silver labels <= 0.5 ring pitch."""
        f = os.path.join(HERE, "data", "photo_reads.csv")
        if not os.path.exists(f):
            self.skipTest("run python -m gauge.run first")
        lab = {r["photo"]: r for r in csv.DictReader(open(os.path.join(HERE, "data", "labels.csv")))}
        e1, e2 = [], []
        for r in csv.DictReader(open(f)):
            l = lab[r["photo"]]
            if not l["first_ring_y"] or not r["first_y"] or not r["pitch_px"]:
                continue
            p = float(r["pitch_px"])
            e1.append(abs(float(r["first_y"]) - float(l["first_ring_y"])) / p)
            e2.append(abs(float(r["last_y"]) - float(l["last_ring_y"])) / p)
        m1, m2 = float(np.median(e1)), float(np.median(e2))
        print(f"\n  median error in pitches: first ring {m1:.2f}, last ring {m2:.2f} (n={len(e1)})")
        self.assertLessEqual(m1, 0.5); self.assertLessEqual(m2, 0.5)


class TestPitch(unittest.TestCase):
    def test_three_of_fourteen_hidden(self):
        im, first, _ = rod(rings=14, p=37, leaves=(4, 5, 9))
        r = read(im, detect(im))
        self.assertLess(abs(r["pitch_px"] - 37) / 37, 0.03)

    def test_wave(self):
        x = (np.sin(np.arange(600) * 2 * np.pi / 31.5) > 0.6).astype(float)
        x[200:290] = 0                                       # a leaf over three rings
        p, _ = pitch(x)
        self.assertLess(abs(p - 31.5) / 31.5, 0.03)


class TestRead(unittest.TestCase):
    def test_known_levels(self):
        for n, p, leaves, sleeve, tilt in [(14, 40, (), "black", 0), (14, 40, (5, 6), "black", 0.05),
                                           (3, 45, (), "black", 0), (20, 30, (8,), "grey", 0), (9, 50, (2,), "black", -0.08)]:
            im, _, _ = rod(rings=n, p=p, leaves=leaves, sleeve=sleeve, tilt=tilt)
            r = read(im, detect(im))
            self.assertLessEqual(abs(r["rings"] - n), 0.3, (n, p, leaves, sleeve, tilt, r))

    def test_no_rings_reads_zero(self):
        im, _, _ = rod(rings=0, p=40)
        self.assertEqual(read(im, detect(im))["rings"], 0)


class TestFuse(unittest.TestCase):
    def test_agree(self):
        f = fuse([dict(rings=14, confidence=0.8), dict(rings=15, confidence=0.4)])
        self.assertEqual(f["flags"], []); self.assertIn(f["rings"], (14.0, 14.5))

    def test_disagree_flagged(self):
        f = fuse([dict(rings=14, confidence=0.8), dict(rings=20, confidence=0.7)])
        self.assertIn("shots disagree", f["flags"]); self.assertEqual(f["rings"], 14)

    def test_missing(self):
        self.assertEqual(fuse([dict(rings=None, confidence=0)])["flags"], ["no rod found"])

    def test_every_visit_read_or_flagged(self):
        f = os.path.join(HERE, "data", "photo_reads.csv")
        if not os.path.exists(f):
            self.skipTest("run python -m gauge.run first")
        from gauge.eval import load, visits
        vs = visits(load(), "rings")
        flagged = sum(bool(o["flags"]) for o in vs)
        print(f"\n  {len(vs)} visits, {flagged} flagged ({100 * flagged / len(vs):.1f}%)")
        self.assertTrue(all(o["rings"] is not None or o["flags"] for o in vs))
        self.assertLessEqual(flagged / len(vs), 0.15)


class TestTimeline(unittest.TestCase):
    def test_spike_flagged(self):
        s = [14, 14.5, 15, 20, 15.5, 16]
        self.assertEqual(timeline(s), [False, False, False, True, False, False])

    def test_drift_not_flagged(self):
        self.assertFalse(any(timeline([10, 11, 12, 13, 14, 15, 16, 17])))

    def test_step_change_not_flagged(self):
        """Irrigation is a real step: the level jumps and stays."""
        self.assertFalse(any(timeline([3, 3, 3, 24, 24, 24])))


class TestV0(unittest.TestCase):
    """The company detector, rebuilt from its description."""
    def test_counts_and_hidden_stripes(self):
        from gauge import v0
        im, _, _ = rod(rings=12, p=40, leaves=(5,))
        o = v0.read(im.astype(np.uint8))
        self.assertEqual(o["cm"], 12)                  # 11 visible + 1 inferred
        self.assertEqual(o["hidden"], 1)
        self.assertEqual(o["level"], 2)                # count minus the 10 cm guide offset
        self.assertEqual(o["state"], "Saturated")

    def test_pitch_ignores_wide_holes(self):
        from gauge import v0
        self.assertAlmostEqual(v0.pitch_of(np.array([40, 41, 120, 39, 40, 200])), 40, delta=1)

    def test_no_stripes_no_reading(self):
        from gauge import v0
        im, _, _ = rod(rings=0)
        self.assertIsNone(v0.read(im.astype(np.uint8))["cm"])


class TestV1(unittest.TestCase):
    def test_bad_gauge(self):
        from gauge import v1
        self.assertTrue(v1.bad_gauge(dict(rings="31", pitch_px="30", half="30")).startswith("bad gauge"))
        self.assertTrue(v1.bad_gauge(dict(rings="10", pitch_px="90", half="30")).startswith("bad gauge"))
        self.assertEqual(v1.bad_gauge(dict(rings="14", pitch_px="30", half="30")), "")
        d = v1.decide(dict(rings="31", pitch_px="30", half="30"), 0.95)
        self.assertFalse(d["accepted"]); self.assertLessEqual(d["confidence"], 0.7)

    def test_model_learns_and_round_trips(self):
        from gauge import v1
        rng = np.random.default_rng(0)
        X = rng.normal(size=(200, len(v1.FEATURES))); y = (X[:, 0] + 0.3 * rng.normal(size=200) > 0).astype(float)
        m = v1.Model().fit(X, y)
        self.assertGreater(((m.prob(X) > 0.5) == y).mean(), 0.85)
        m2 = v1.Model.from_json(m.to_json())
        self.assertTrue(np.allclose(m.prob(X), m2.prob(X)))

    def test_folder_rule(self):
        from gauge import v1
        self.assertEqual(v1.folder([dict(cm=14, accepted=True), dict(cm=16, accepted=True)])["cm"], 15)
        self.assertEqual(v1.folder([dict(cm=14, accepted=False)])["state"], "review")


if __name__ == "__main__":
    unittest.main()
