"""gate.py の境界値・失敗時の試験(一時ディレクトリだけ・合成の合言葉だけ)。実行: python3 -m unittest discover -s tests -v

test_gate.py が「ふつうに使ったときの流れ」、こちらは「端・壊れたとき・細工された入力」を見る。
どれも「迷ったら閉じる(中身を見せない)」になっていることを確かめる。
"""
import json
import os
import shutil
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gate  # noqa: E402

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ImportError:   # pragma: no cover
    FastAPI = None

PW = "goukaku-no-kotoba-7"   # 作り物
HDR = {"X-Requested-With": "t"}


def make_app(data_dir_fn):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    gate.install(app, data_dir_fn, cookie="t_gate", title="試験", header="t")

    @app.get("/api/x")
    def x():
        return {"secret": "yes"}

    @app.post("/api/x")
    def post_x():
        return {"ok": True}

    @app.get("/page")
    def page():
        return {"secret": "page"}

    return app


@unittest.skipIf(FastAPI is None, "fastapi が無い")
class GateEdgeBase(unittest.TestCase):
    def setUp(self):
        gate._fails.clear()
        self.addCleanup(gate._fails.clear)
        self.tmp = Path(tempfile.mkdtemp(prefix="gate-edge-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.app = make_app(lambda: self.tmp)
        self.c = TestClient(self.app, raise_server_exceptions=False)

    def login(self, pw, client=None, **kw):
        return (client or self.c).post("/login", json={"password": pw}, headers={**HDR, **kw.pop("headers", {})}, **kw)


class LockoutTest(GateEdgeBase):
    """連続失敗のロック: LOCK_WINDOW 秒の中で LOCK_FAILS 回目までは試せる・それを超えたら正しい合言葉でも 429。"""

    def setUp(self):
        super().setUp()
        gate.set_password(self.tmp, PW)

    def test_one_below_limit_still_allows_login(self):
        for _ in range(gate.LOCK_FAILS - 1):
            self.assertEqual(self.login("wrong").status_code, 401)
        self.assertEqual(self.login(PW).status_code, 200)

    def test_at_limit_even_correct_password_is_refused(self):
        for _ in range(gate.LOCK_FAILS):
            self.login("wrong")
        r = self.login(PW)
        self.assertEqual(r.status_code, 429)
        self.assertNotIn("set-cookie", r.headers)
        self.assertEqual(self.login("wrong").status_code, 429)   # ロック中の失敗は数を増やさない(429 で止まる)
        self.assertEqual(len(gate._fails), gate.LOCK_FAILS)

    def test_lock_lifts_after_window(self):
        t0 = 1_900_000_000.0
        with mock.patch.object(gate.time, "time", return_value=t0):
            for _ in range(gate.LOCK_FAILS):
                self.login("wrong")
            self.assertEqual(self.login(PW).status_code, 429)
        with mock.patch.object(gate.time, "time", return_value=t0 + gate.LOCK_WINDOW - 1):
            self.assertEqual(self.login(PW).status_code, 429)     # 窓の端の1秒前はまだロック
        with mock.patch.object(gate.time, "time", return_value=t0 + gate.LOCK_WINDOW):
            self.assertEqual(self.login(PW).status_code, 200)     # 窓を過ぎたら古い失敗は数えない

    def test_request_without_header_is_not_counted(self):
        for _ in range(gate.LOCK_FAILS + 2):
            r = self.c.post("/login", json={"password": "wrong"})
            self.assertEqual(r.status_code, 403)
        self.assertEqual(gate._fails, [])
        self.assertEqual(self.login(PW).status_code, 200)

    def test_malformed_bodies_fail_and_count(self):
        bodies = [b"not json", b"[1,2]", b'"just a string"', b"{}", b'{"password": null}', b""]
        for b in bodies:
            r = self.c.post("/login", content=b, headers={**HDR, "Content-Type": "application/json"})
            self.assertEqual(r.status_code, 401, b)
        self.assertEqual(len(gate._fails), len(bodies))

    def test_non_ascii_password_round_trip(self):
        gate.set_password(self.tmp, "日本語の合言葉🔑")
        self.assertEqual(self.login("日本語の合言葉").status_code, 401)
        self.assertEqual(self.login("日本語の合言葉🔑").status_code, 200)


class CookieTest(GateEdgeBase):
    """署名つき cookie: 期限・改ざん・属性。"""

    def setUp(self):
        super().setUp()
        gate.set_password(self.tmp, PW)
        self.secret = json.loads(gate.gate_path(self.tmp).read_text())["secret"]

    def with_cookie(self, value):
        c = TestClient(self.app, raise_server_exceptions=False)
        c.cookies.set("t_gate", value)
        return c.get("/api/x")

    def test_expiry_boundary(self):
        now = 1_900_000_000
        with mock.patch.object(gate.time, "time", return_value=float(now)):
            self.assertTrue(gate._valid_cookie(self.secret, f"{now + 1}.{gate._sign(self.secret, now + 1)}"))
            self.assertFalse(gate._valid_cookie(self.secret, f"{now}.{gate._sign(self.secret, now)}"))      # ちょうど期限 = 切れ
            self.assertFalse(gate._valid_cookie(self.secret, f"{now - 1}.{gate._sign(self.secret, now - 1)}"))

    def test_tampered_or_malformed_cookies_are_rejected(self):
        exp = int(time.time()) + 3600
        good = gate._sign(self.secret, exp)
        cases = {
            "empty": "",
            "no dot": f"{exp}{good}",
            "exp not int": f"abc.{good}",
            "exp changed": f"{exp + 1}.{good}",
            "sig changed": f"{exp}.{good[:-1]}{'0' if good[-1] != '0' else '1'}",
            "sig truncated": f"{exp}.{good[:32]}",
            "other secret": f"{exp}.{gate._sign('0' * 64, exp)}",
            "sig empty": f"{exp}.",
        }
        for name, value in cases.items():
            with self.subTest(name):
                r = self.with_cookie(value)
                self.assertEqual(r.status_code, 401)
                self.assertNotIn("secret", r.text)
        self.assertEqual(self.with_cookie(f"{exp}.{good}").status_code, 200)   # 本物だけ通る

    def test_non_ascii_cookie_is_401_not_500(self):
        # cookie は外から来る。ASCII 以外の文字でも例外(500)にせず、ふつうに断る
        self.assertFalse(gate._valid_cookie(self.secret, f"{int(time.time()) + 60}.é"))
        r = self.c.get("/api/x", headers={"Cookie": b"t_gate=9999999999.\xc3\xa9"})
        self.assertEqual(r.status_code, 401)

    def test_cookie_attributes_over_http(self):
        sc = self.login(PW).headers["set-cookie"]
        low = sc.lower()
        for part in ("httponly", "samesite=lax", f"max-age={gate.MAX_AGE}", "path=/"):
            self.assertIn(part, low)
        self.assertNotIn("secure", low.replace("httponly", ""))
        self.assertNotIn(PW, sc)

    def test_secure_flag_behind_https(self):
        https = TestClient(self.app, base_url="https://testserver")
        self.assertIn("secure", self.login(PW, client=https).headers["set-cookie"].lower())
        via_proxy = self.login(PW, headers={"X-Forwarded-Proto": "https"}).headers["set-cookie"]
        self.assertIn("secure", via_proxy.lower())

    def test_logout_clears_cookie(self):
        self.login(PW)
        self.assertEqual(self.c.get("/api/x").status_code, 200)
        self.assertEqual(self.c.post("/logout").status_code, 403)          # 確認ヘッダーなしの logout も断る
        r = self.c.post("/logout", headers=HDR)
        self.assertEqual(r.status_code, 200)
        self.assertIn("t_gate=", r.headers["set-cookie"])
        self.assertEqual(self.c.get("/api/x").status_code, 401)


class FailClosedTest(GateEdgeBase):
    """設定が無い・壊れている・途中で消えた → 中身を見せず 503。"""

    def assertClosed(self):
        for path in ("/api/x", "/page", "/login"):
            r = self.c.get(path)
            self.assertEqual(r.status_code, 503, path)
            self.assertNotIn("secret", r.text)
        self.assertEqual(self.c.post("/login", json={"password": PW}, headers=HDR).status_code, 503)

    def test_broken_gate_json_variants(self):
        bad = {
            "not json": "{",
            "list": "[1, 2]",
            "empty object": "{}",
            "missing secret": json.dumps({"v": 1, "salt": "00", "hash": "ab"}),
            "salt not hex": json.dumps({"v": 1, "salt": "zz", "hash": "ab", "secret": "s"}),
            "empty hash": json.dumps({"v": 1, "salt": "00", "hash": "", "secret": "s"}),
            "number fields": json.dumps({"v": 1, "salt": 1, "hash": 2, "secret": 3}),
        }
        for name, text in bad.items():
            with self.subTest(name):
                gate.gate_path(self.tmp).write_text(text)
                self.assertIsNone(gate._load(self.tmp))
                self.assertClosed()

    def test_gate_json_removed_after_login(self):
        gate.set_password(self.tmp, PW)
        self.login(PW)
        self.assertEqual(self.c.get("/api/x").status_code, 200)
        gate.gate_path(self.tmp).unlink()
        self.assertClosed()

    def test_unreadable_data_dir(self):
        self.c = TestClient(make_app(lambda: self.tmp / "no-such-dir"), raise_server_exceptions=False)
        self.assertClosed()


class ResponseShapeTest(GateEdgeBase):
    """未ログインのときの返し方と、通したときに足すヘッダー。"""

    def setUp(self):
        super().setUp()
        gate.set_password(self.tmp, PW)

    def test_unauthenticated_api_is_json_401_and_page_is_login_form(self):
        r = self.c.get("/api/x")
        self.assertEqual((r.status_code, r.json()), (401, {"error": "login"}))
        r = self.c.get("/page")
        self.assertEqual(r.status_code, 200)
        self.assertIn('type="password"', r.text)
        self.assertNotIn("secret", r.text)
        self.assertIn("'X-Requested-With':'t'", r.text)   # ログイン画面の fetch が確認ヘッダーを付ける

    def test_wrong_header_value_is_forbidden(self):
        self.login(PW)
        for h in ({}, {"X-Requested-With": "XMLHttpRequest"}, {"X-Requested-With": "T"}, {"X-Requested-With": ""}):
            with self.subTest(h):
                self.assertEqual(self.c.post("/api/x", headers=h).status_code, 403)

    def test_cache_and_robots_headers(self):
        self.login(PW)
        api, page = self.c.get("/api/x"), self.c.get("/page")
        self.assertEqual(api.headers["cache-control"], "no-store")
        self.assertEqual(page.headers["cache-control"], "no-cache")
        self.assertEqual(api.headers["x-robots-tag"], "noindex")
        # HEAD は読むだけなので確認ヘッダーなしでもゲートは通す(先のアプリが GET だけなら 405 になるのは FastAPI 側の動き)
        self.assertNotIn(self.c.head("/page").status_code, (401, 403))


class OpenFlagTest(GateEdgeBase):
    """gate-open(合言葉なし)のときも、書き込みの確認ヘッダーは残る。"""

    def setUp(self):
        super().setUp()
        (self.tmp / gate.OPEN_FLAG).touch()

    def test_login_page_redirects_home(self):
        r = self.c.get("/login", follow_redirects=False)
        self.assertIn(r.status_code, (302, 307))
        self.assertEqual(r.headers["location"], "/")

    def test_login_logout_are_noops_but_still_need_header(self):
        self.assertEqual(self.c.post("/login", json={}).status_code, 403)
        self.assertEqual(self.c.post("/login", json={}, headers=HDR).json(), {"ok": True})
        self.assertEqual(self.c.post("/logout", headers=HDR).json(), {"ok": True})

    def test_writes_with_header_pass_and_headers_are_set(self):
        r = self.c.post("/api/x", headers=HDR)
        self.assertEqual(r.json(), {"ok": True})
        self.assertEqual(r.headers["cache-control"], "no-store")
        self.assertEqual(r.headers["x-robots-tag"], "noindex")

    def test_removing_flag_closes_again(self):
        gate.set_password(self.tmp, PW)
        self.assertEqual(self.c.get("/api/x").status_code, 200)
        (self.tmp / gate.OPEN_FLAG).unlink()
        self.assertEqual(self.c.get("/api/x").status_code, 401)


class SetPasswordFileTest(unittest.TestCase):
    """gate.json の書き方: 600・途中のファイルを残さない・古い権限を引き継がない。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gate-file-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_mode_600_even_with_permissive_umask(self):
        old = os.umask(0)
        try:
            gate.set_password(self.tmp / "d", PW)
        finally:
            os.umask(old)
        self.assertEqual(stat.S_IMODE(gate.gate_path(self.tmp / "d").stat().st_mode), 0o600)

    def test_replaces_world_readable_file(self):
        p = gate.gate_path(self.tmp)
        p.write_text("{}")
        p.chmod(0o644)
        gate.set_password(self.tmp, PW)
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
        self.assertEqual([x.name for x in self.tmp.iterdir()], ["gate.json"])   # .tmp を残さない

    def test_salt_and_secret_are_fresh_each_time(self):
        gate.set_password(self.tmp, PW)
        a = json.loads(gate.gate_path(self.tmp).read_text())
        gate.set_password(self.tmp, PW)
        b = json.loads(gate.gate_path(self.tmp).read_text())
        self.assertNotEqual(a["salt"], b["salt"])
        self.assertNotEqual(a["hash"], b["hash"])        # 同じ合言葉でもハッシュは毎回違う
        self.assertNotEqual(a["secret"], b["secret"])
        self.assertEqual(len(bytes.fromhex(a["salt"])), 16)
        self.assertEqual(len(a["secret"]), 64)


if __name__ == "__main__":
    unittest.main()
