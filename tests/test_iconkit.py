"""iconkit / gate(icon=) / http.server 用 serve の試験(一時ディレクトリだけ。実データには触れない)。
実行: python3 -m unittest discover -s tests -v   (FastAPI と httpx が要る)
アイコン自体は先に `python3 icons.py` で作っておく。"""
import json
import os
import shutil
import struct
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import iconkit  # noqa: E402

APPS = [i for i, m in iconkit.META.items() if m["png"]]
PATHS = {"/apple-touch-icon.png": (180, "image/png"), "/apple-touch-icon-precomposed.png": (180, "image/png"),
         "/icon-192.png": (192, "image/png"), "/icon-512.png": (512, "image/png")}


def png_info(b):
    assert b[:8] == b"\x89PNG\r\n\x1a\n"
    w, h, depth, ctype = struct.unpack(">IIBB", b[16:26])
    return w, h, depth, ctype


class KitTest(unittest.TestCase):
    def test_every_app_icon_exists_and_is_opaque_rgb(self):
        for i in APPS:
            for path, (size, ctype) in PATHS.items():
                r = iconkit.lookup(i, path)
                self.assertIsNotNone(r, (i, path))
                self.assertEqual(r[1]["Content-Type"], ctype)
                self.assertEqual(png_info(r[0]), (size, size, 8, 2), (i, path))   # 透過なし(RGB)
                self.assertEqual(r[1]["Cache-Control"], "public, max-age=86400")
            svg = iconkit.lookup(i, "/favicon.svg")
            self.assertIn(b"<svg", svg[0])
            self.assertEqual(svg[1]["Content-Type"], "image/svg+xml")

    def test_tile_only_icons_have_svg_but_no_png(self):
        for i, m in iconkit.META.items():
            if not m["png"]:
                self.assertIsNotNone(iconkit.lookup(i, "/favicon.svg"), i)
                self.assertIsNone(iconkit.lookup(i, "/apple-touch-icon.png"), i)

    def test_manifest(self):
        m = json.loads(iconkit.lookup("money", "/manifest.webmanifest")[0])
        self.assertEqual((m["short_name"], m["start_url"], m["display"]), ("家計", "/", "standalone"))
        # iOS は SVG を使えないので PNG だけ(180/192/512)
        self.assertEqual([x["sizes"] for x in m["icons"]], ["180x180", "192x192", "512x512"])
        self.assertTrue(all(x["type"] == "image/png" for x in m["icons"]))
        self.assertTrue(m["theme_color"].startswith("#") and m["background_color"].startswith("#"))

    def test_other_paths_not_served(self):
        for p in ("/", "/api/state", "/static/icon.svg", "/icon-1024.png", "/../gate.py"):
            self.assertIsNone(iconkit.lookup("money", p), p)
        self.assertIsNone(iconkit.lookup("nope", "/favicon.svg"))

    def test_fa_js_served_publicly(self):
        for p, mark in (("/kit/fa.js", b"Font Awesome"), ("/kit/fa-emoji.js", b"MAP")):
            r = iconkit.lookup("money", p)
            self.assertIsNotNone(r, p)
            self.assertIn(mark, r[0])
            self.assertTrue(r[1]["Content-Type"].startswith("application/javascript"))
        self.assertIsNone(iconkit.lookup("money", "/kit/gate.py"))
        self.assertIsNone(iconkit.lookup("money", "/kit/../gate.py"))

    def test_head_tags(self):
        t = iconkit.head_tags("progress")
        for s in ('rel="apple-touch-icon" sizes="180x180" href="/icon-v3-180.png"', 'rel="icon" type="image/svg+xml" href="/favicon.svg"',
                  'rel="manifest" href="/manifest.webmanifest"', 'apple-mobile-web-app-title" content="進み具合"'):
            self.assertIn(s, t)

    def test_icons_are_distinct(self):
        seen = {}
        for i in APPS:
            b = iconkit.lookup(i, "/icon-512.png")[0]
            self.assertNotIn(b, seen.values(), i)
            seen[i] = b


class LookupEdgeTest(unittest.TestCase):
    """公開パスの境界: 完全一致だけ・GET/HEAD だけ・ファイルが無ければ None(例外にしない)。"""

    def test_only_exact_paths(self):
        for p in ("/Favicon.svg", "/favicon.svg/", "//favicon.svg", "/favicon.svg%00", "/%2e%2e/gate.py", "/kit/", "/kit/kit.css", "/icons/money.svg", ""):
            self.assertIsNone(iconkit.lookup("money", p), p)
        self.assertIsNotNone(iconkit.lookup("money", "/favicon.svg?v=9&x=1"))   # クエリは無視する

    def test_response_refuses_non_read_methods(self):
        for m in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS"):
            self.assertIsNone(iconkit.response("money", "/favicon.svg", m), m)
        self.assertIsNotNone(iconkit.response("money", "/favicon.svg", "HEAD"))

    def test_missing_files_return_none(self):
        empty = Path(tempfile.mkdtemp(prefix="iconkit-empty-"))
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        with mock.patch.object(iconkit, "ICON_DIR", empty), mock.patch.dict(iconkit._cache, clear=True):
            self.assertIsNone(iconkit.lookup("money", "/favicon.svg"))
            self.assertIsNone(iconkit.lookup("money", "/icon-512.png"))
            self.assertIsNotNone(iconkit.lookup("money", "/manifest.webmanifest"))   # manifest はファイルに頼らない

    def test_cache_follows_file_changes(self):
        d = Path(tempfile.mkdtemp(prefix="iconkit-cache-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        f = d / "money.svg"
        with mock.patch.object(iconkit, "ICON_DIR", d), mock.patch.dict(iconkit._cache, clear=True):
            f.write_bytes(b"<svg>1</svg>")
            os.utime(f, (1_000_000, 1_000_000))
            self.assertEqual(iconkit.lookup("money", "/favicon.svg")[0], b"<svg>1</svg>")
            f.write_bytes(b"<svg>2</svg>")
            os.utime(f, (1_000_100, 1_000_100))
            self.assertEqual(iconkit.lookup("money", "/favicon.svg")[0], b"<svg>2</svg>")

    def test_tile_only_manifest_uses_svg(self):
        m = json.loads(iconkit.manifest("monitor"))
        self.assertEqual([(x["src"], x["type"]) for x in m["icons"]], [("/favicon.svg", "image/svg+xml")])


class HttpServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_HEAD(self):
                if not iconkit.serve(self, "progress"):
                    self.send_error(404)

            def do_GET(self):
                if iconkit.serve(self, "progress"):
                    return
                self.send_error(404)

            def do_POST(self):
                if iconkit.serve(self, "progress"):
                    return
                self.send_error(405)

        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def get(self, path, method="GET"):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, b"", dict(e.headers)

    def test_serve(self):
        st, body, h = self.get("/apple-touch-icon.png?v=1")
        self.assertEqual((st, h["Content-Type"], png_info(body)[:2]), (200, "image/png", (180, 180)))
        st, body, h = self.get("/apple-touch-icon.png", "HEAD")
        self.assertEqual((st, body), (200, b""))
        self.assertEqual(int(h["Content-Length"]), len(iconkit.lookup("progress", "/apple-touch-icon.png")[0]))
        self.assertEqual(self.get("/api/list")[0], 404)
        self.assertEqual(self.get("/apple-touch-icon.png", "POST")[0], 405)   # GET/HEAD 以外は返さない


class GateIconTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        import gate
        cls.tmp = Path(tempfile.mkdtemp(prefix="gate-icon-test-"))
        gate.set_password(cls.tmp, "pw-test")
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        gate.install(app, lambda: cls.tmp, cookie="t_gate", title="試験", header="t", icon="notes")

        @app.get("/")
        def index():
            return {"secret": "yes"}

        @app.get("/api/x")
        def x():
            return {"secret": "yes"}

        plain = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        gate.install(plain, lambda: cls.tmp, cookie="t_gate", title="試験", header="t")   # icon なし=今まで通り
        cls.c, cls.plain = TestClient(app), TestClient(plain)

    def test_public_icons_before_auth(self):
        for path, (size, ctype) in PATHS.items():
            r = self.c.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertTrue(r.headers["content-type"].startswith(ctype))
            self.assertEqual(png_info(r.content)[:2], (size, size))
        self.assertEqual(self.c.get("/favicon.svg").status_code, 200)
        self.assertEqual(self.c.get("/manifest.webmanifest").json()["short_name"], "メモ")
        self.assertEqual(self.c.head("/apple-touch-icon.png").status_code, 200)

    def test_everything_else_still_needs_login(self):
        self.assertEqual(self.c.get("/api/x").status_code, 401)
        r = self.c.get("/")
        self.assertIn("合言葉", r.text)
        self.assertNotIn("secret", r.text)
        self.assertIn('rel="apple-touch-icon"', r.text)          # ログイン画面にもアイコンの指定
        self.assertEqual(self.c.post("/apple-touch-icon.png").status_code, 403)

    def test_without_icon_arg_nothing_changes(self):
        self.assertNotIn("apple-touch-icon", self.plain.get("/").text)
        self.assertIn("合言葉", self.plain.get("/apple-touch-icon.png").text)    # 今まで通りログイン画面


if __name__ == "__main__":
    unittest.main()
