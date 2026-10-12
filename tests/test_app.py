"""python -m unittest tests/test_app.py   Demo app: sign-in, roles, sessions, lockout, uploads, routes."""
import io, json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.update(CM_ADMIN_PIN="111111", CM_USER_PIN="222222", CM_SECRET="test-secret")
from gauge import web


def call(path, method="GET", body=b"", cookie="", ip="1.2.3.4"):
    out = {}
    env = {"PATH_INFO": path, "REQUEST_METHOD": method, "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body),
           "HTTP_COOKIE": cookie, "REMOTE_ADDR": ip, "wsgi.url_scheme": "http"}
    resp = b"".join(web.app(env, lambda s, h: out.update(status=int(s.split()[0]), headers=dict(h))))
    return out["status"], out["headers"], resp


def login(pin, ip="9.9.9.9"):
    s, h, _ = call("/api/login", "POST", json.dumps(dict(pin=pin)).encode(), ip=ip)
    return s, h.get("Set-Cookie", "").split(";")[0]


class TestAuth(unittest.TestCase):
    def setUp(self):
        web._fails.clear()

    def test_signed_out(self):
        s, _, b = call("/api/me")
        self.assertEqual(s, 200); self.assertIsNone(json.loads(b)["role"])
        self.assertEqual(call("/api/gallery")[0], 401)
        self.assertEqual(call("/api/photo/000.jpg")[0], 401)
        self.assertEqual(call("/api/read", "POST", b"\xff\xd8\xff")[0], 401)

    def test_wrong_pin_and_lockout(self):
        for _ in range(4):
            self.assertEqual(login("000000", ip="5.5.5.5")[0], 401)
        self.assertEqual(login("000000", ip="5.5.5.5")[0], 401)       # 5th wrong PIN starts the lock
        self.assertEqual(login("111111", ip="5.5.5.5")[0], 429)       # even the right PIN waits 60 s
        self.assertEqual(login("111111", ip="6.6.6.6")[0], 200)       # other clients unaffected

    def test_roles(self):
        _, user = login("222222")
        _, admin = login("111111")
        self.assertEqual(call("/api/gallery", cookie=user)[0], 200)
        self.assertEqual(call("/api/export.csv", cookie=user)[0], 403)
        self.assertEqual(call("/api/corrections", cookie=user)[0], 403)
        self.assertEqual(call("/api/export.csv", cookie=admin)[0], 200)
        self.assertEqual(json.loads(call("/api/me", cookie=admin)[2])["role"], "admin")

    def test_tampered_and_expired_session(self):
        _, user = login("222222")
        tok = user.split("=", 1)[1]
        body, sig = tok.rsplit(".", 1)
        forged = web.base64.urlsafe_b64encode(b'{"role": "admin", "exp": 9999999999}').decode() + "." + sig
        self.assertEqual(call("/api/export.csv", cookie="cm_session=" + forged)[0], 401)
        self.assertIsNone(web.verify(web.sign("user", now=0)))      # issued at epoch 0: long expired
        self.assertIsNone(web.verify("garbage"))


class TestRoutes(unittest.TestCase):
    def setUp(self):
        web._fails.clear()
        self.user = login("222222")[1]

    def test_gallery_and_photo(self):
        g = json.loads(call("/api/gallery", cookie=self.user)[2])
        self.assertEqual(len(g["photos"]), 127)
        s, h, b = call("/api/photo/000.jpg", cookie=self.user)
        self.assertEqual(s, 200); self.assertEqual(h["Content-Type"], "image/jpeg"); self.assertEqual(b[:3], b"\xff\xd8\xff")
        self.assertEqual(call("/api/photo/../../data/labels.csv", cookie=self.user)[0], 404)

    def test_upload_checks(self):
        self.assertEqual(call("/api/read", "POST", b"hello", cookie=self.user)[0], 415)
        self.assertEqual(call("/api/correct", "POST", b'{"id":"../x","rings":3}', cookie=self.user)[0], 400)
        self.assertEqual(call("/api/correct", "POST", b'{"id":"001","rings":99}', cookie=self.user)[0], 400)

    def test_live_read(self):
        from tests.test_gauge import rod
        from PIL import Image
        import numpy as np
        im, _, _ = rod(rings=12, p=40)
        buf = io.BytesIO(); Image.fromarray(im.astype(np.uint8)).save(buf, "JPEG", quality=92)
        s, _, b = call("/api/read", "POST", buf.getvalue(), cookie=self.user)
        d = json.loads(b)
        self.assertEqual(s, 200); self.assertEqual(d["cm"], 12)

    def test_static_and_traversal(self):
        self.assertEqual(call("/../data/labels.csv")[0], 404)


if __name__ == "__main__":
    unittest.main()
