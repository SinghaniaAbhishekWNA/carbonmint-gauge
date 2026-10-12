"""python -m unittest discover -s service/tests   (from the repo root; needs jsonschema for the report check)
Zip handling, visit grouping, damaged photos, hostile names, limits, soil rules, report schema, folder watcher.
Photos are synthetic gauges with known stripe counts (tests/test_gauge.rod)."""
import io, json, os, shutil, sys, tempfile, unittest, zipfile
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(REPO), str(REPO / "service"), str(REPO / "tests")]
from test_gauge import rod                     # noqa: E402
from gaugesvc import batch, engine, watch      # noqa: E402

V1 = "AIT-CP-5286-2931-CKP K26 NG - 011026101600"
V2 = "GAN-CP-2670-3131-CKP K26 SD - 021026120238"


def jpg(rings=14, p=40, **kw):
    im, _, _ = rod(rings=rings, p=p, **kw)
    b = io.BytesIO(); Image.fromarray(im.clip(0, 255).astype("uint8")).save(b, "JPEG", quality=95)
    return b.getvalue()


def make_zip(path, members):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in members:
            z.writestr(name, data)
    return path


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestZip(Base):
    def test_visits_damaged_hostile_and_loose(self):
        z = make_zip(self.tmp / "a.zip", [
            (f"way points/{V1}/a_photo.jpg", jpg(14)), (f"way points/{V1}/b_photo.jpg", jpg(14, tilt=0.03)),
            (f"way points/{V2}/c_photo.jpg", jpg(9)), (f"way points/{V2}/d_photo.jpg", b"not a jpeg"),
            ("loose_photo.JPG", jpg(20, p=30)), ("../evil.jpg", jpg(5)), ("C:/evil2.jpg", jpg(5)), ("notes.txt", b"hi")])
        rep = batch.run(z)
        photos = {p["file"]: p for p in rep["photos"]}
        self.assertEqual(rep["summary"]["photos"], 5)
        self.assertEqual(rep["summary"]["visits"], 3)
        self.assertEqual({s["name"]: s["reason"] for s in rep["skipped"]},
                         {"../evil.jpg": "unsafe path", "C:/evil2.jpg": "unsafe path", "notes.txt": "not a jpg or png"})
        self.assertEqual(photos[f"way points/{V2}/d_photo.jpg"]["status"], "error")       # one bad photo, batch goes on
        for n, want in ((f"way points/{V1}/a_photo.jpg", 14), (f"way points/{V2}/c_photo.jpg", 9), ("loose_photo.JPG", 20)):
            got = photos[n]["stripes"] if photos[n]["stripes"] is not None else photos[n].get("candidate_stripes")
            self.assertEqual(got, want, (n, photos[n]))
        self.assertIn("no_twin_shot", photos["loose_photo.JPG"]["flags"])
        self.assertIn("twin_unreadable", photos[f"way points/{V2}/c_photo.jpg"]["flags"])
        v = {x["folder"]: x for x in rep["visits"]}[f"way points/{V1}"]
        self.assertEqual((v["checkpoint"], v["taken"]), ("AIT-CP-5286-2931-CKP K26 NG", "2026-10-01T10:16:00"))
        self.check_schema(rep)

    def check_schema(self, rep):
        import jsonschema
        jsonschema.validate(json.loads(json.dumps(rep)), json.load(open(REPO / "service/report.schema.json")))

    def test_big_folder_is_not_one_visit(self):
        z = make_zip(self.tmp / "b.zip", [(f"{V1}/{i}.jpg", jpg(14)) for i in range(5)])
        rep = batch.run(z)
        self.assertEqual(rep["summary"]["visits"], 5)
        self.assertTrue(all("no_twin_shot" in p["flags"] for p in rep["photos"]))

    def test_rejected_zips(self):
        with self.assertRaises(batch.ZipRejected):
            batch.run(make_zip(self.tmp / "empty.zip", []))
        with self.assertRaises(batch.ZipRejected):
            batch.run(make_zip(self.tmp / "txt.zip", [("a.txt", b"x")]))
        (self.tmp / "broken.zip").write_bytes(b"PK\x03\x04 broken")
        with self.assertRaises(batch.ZipRejected):
            batch.run(self.tmp / "broken.zip")
        old = batch.MAX_IMAGES
        batch.MAX_IMAGES = 2
        try:
            with self.assertRaises(batch.ZipRejected):
                batch.run(make_zip(self.tmp / "many.zip", [(f"{i}.jpg", b"x") for i in range(3)]))
        finally:
            batch.MAX_IMAGES = old


class TestRules(unittest.TestCase):
    def test_soil_state(self):
        self.assertEqual(engine.level(24), (24.0, 14.0, "Flooded"))
        self.assertEqual(engine.level(10), (10.0, 0.0, "Saturated"))
        self.assertEqual(engine.level(5), (5.0, -5.0, "Drying"))
        self.assertEqual(engine.level(0), (0.0, -10.0, "Drying"))      # dry gauge: -10 cm by the guide rule
        self.assertEqual(engine.level(None), (None, None, None))

    def test_visit_reading_is_mean_of_accepted(self):
        r, ok = engine.visit_reading([dict(status="accepted", stripes=14), dict(status="accepted", stripes=15),
                                      dict(status="review", stripes=None)])
        self.assertEqual((r["stripes"], ok), (14.5, True))
        r, ok = engine.visit_reading([dict(status="review", stripes=None)])
        self.assertEqual((r["status"], ok), ("review", None))


class TestWatcher(Base):
    def setUp(self):
        super().setUp()
        self.w = watch.Watcher(self.tmp / "in", self.tmp / "out")
        watch.HEARTBEAT = self.tmp / "hb"

    def test_waits_for_copy_then_reads_once(self):
        z = self.tmp / "in" / "batch.zip"
        z.write_bytes(b"PK")                                   # copy still in progress
        self.assertEqual(self.w.once(), [])
        make_zip(z, [(f"{V1}/a.jpg", jpg(14)), (f"{V1}/b.jpg", jpg(14))])
        self.assertEqual(self.w.once(), [])                    # size changed since the last look
        self.assertEqual(self.w.once(), ["done"])
        rep = json.loads((self.tmp / "out" / "batch.report.json").read_text())
        self.assertEqual(rep["summary"]["photos"], 2)
        self.assertEqual((rep["schema_version"], rep["engine"]["version"]), ("1.0", "1.0.0"))
        self.assertTrue((self.tmp / "in" / "done" / "batch.zip").exists())
        shutil.copy(self.tmp / "in" / "done" / "batch.zip", self.tmp / "in" / "again.zip")
        self.w.once()
        self.assertEqual(self.w.once(), ["duplicate"])          # same fingerprint: not read twice
        self.assertFalse((self.tmp / "out" / "again.report.json").exists())
        self.assertTrue(watch.healthy())

    def test_broken_zip_goes_to_failed(self):
        (self.tmp / "in" / "bad.zip").write_bytes(b"this is not a zip")
        self.w.once()
        self.assertEqual(self.w.once(), ["failed"])
        self.assertTrue((self.tmp / "in" / "failed" / "bad.zip").exists())
        err = json.loads((self.tmp / "out" / "bad.error.json").read_text())
        self.assertIn("not a readable zip", err["error"])
        self.assertEqual(len(err["sha256"]), 64)

    def test_watcher_survives_restart(self):
        z = make_zip(self.tmp / "in" / "x.zip", [(f"{V1}/a.jpg", jpg(14))])
        self.w.once(); self.w.once()
        w2 = watch.Watcher(self.tmp / "in", self.tmp / "out")   # fingerprints are kept in OUT
        shutil.copy(self.tmp / "in" / "done" / "x.zip", z)
        w2.once()
        self.assertEqual(w2.once(), ["duplicate"])


if __name__ == "__main__":
    unittest.main()
