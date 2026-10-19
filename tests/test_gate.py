"""gate.py の試験(一時ディレクトリだけ)。実行: python3 -m unittest discover -s tests -v"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gate  # noqa: E402

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ImportError:   # pragma: no cover
    FastAPI = None


@unittest.skipIf(FastAPI is None, "fastapi が無い")
class GateTest(unittest.TestCase):
    def setUp(self):
        gate._fails.clear()
        self.tmp = Path(tempfile.mkdtemp(prefix="gate-test-"))
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        gate.install(app, lambda: self.tmp, cookie="t_gate", title="試験", header="t")

        @app.get("/api/x")
        def x():
            return {"secret": "yes"}

        @app.post("/api/x")
        def post_x():
            return {"ok": True}

        self.c = TestClient(app)

    def login(self, pw):
        return self.c.post("/login", json={"password": pw}, headers={"X-Requested-With": "t"})

    def test_closed_when_password_unset(self):
        r = self.c.get("/api/x")
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("secret", r.text)

    def test_hash_only_and_file_mode(self):
        gate.set_password(self.tmp, "pw-test")
        g = json.loads(gate.gate_path(self.tmp).read_text())
        self.assertNotIn("pw-test", json.dumps(g))
        self.assertEqual(gate.gate_path(self.tmp).stat().st_mode & 0o777, 0o600)

    def test_login_flow(self):
        gate.set_password(self.tmp, "pw-test")
        self.assertEqual(self.c.get("/api/x").status_code, 401)
        self.assertEqual(self.login("wrong").status_code, 401)
        self.assertEqual(self.login("pw-test").status_code, 200)
        self.assertEqual(self.c.get("/api/x").json(), {"secret": "yes"})
        self.assertEqual(self.c.post("/api/x").status_code, 403)                                   # 確認ヘッダーなしの書き込み
        self.assertEqual(self.c.post("/api/x", headers={"X-Requested-With": "t"}).status_code, 200)

    def test_password_change_invalidates_cookies(self):
        gate.set_password(self.tmp, "pw-test")
        self.login("pw-test")
        gate.set_password(self.tmp, "pw-new")
        self.assertEqual(self.c.get("/api/x").status_code, 401)

    def test_lockout_after_repeated_failures(self):
        gate.set_password(self.tmp, "pw-test")
        for _ in range(8):
            self.login("wrong")
        self.assertEqual(self.login("pw-test").status_code, 429)

    def test_open_flag(self):
        (self.tmp / gate.OPEN_FLAG).touch()
        self.assertEqual(self.c.get("/api/x").json(), {"secret": "yes"})
        self.assertEqual(self.c.post("/api/x").status_code, 403)   # 書き込みの確認は残る


if __name__ == "__main__":
    unittest.main()
