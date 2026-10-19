"""アイコンの配り方(標準ライブラリのみ。FastAPI/Starlette・http.server・aiohttp から使える)。

アイコン本体は `icons.py` が `dashkit/icons/<id>.svg` `<id>-180/192/512.png` に作る。ここは
- 「認証なしで取れる公開パス」を返す(ログインゲートの後ろの画面でも、iOS が認証なしで取りに来るため)
    /apple-touch-icon.png  /apple-touch-icon-precomposed.png (180)  /icon-192.png  /icon-512.png  /favicon.svg  /manifest.webmanifest
- <head> に入れる HTML 断片を作る(head_tags)

使い方:
    FastAPI(ゲートなし):  iconkit.install(app, "notes")
    FastAPI(gate.py):     gate.install(app, ..., icon="money")   ← 認証より前に返す
    http.server:          do_GET の先頭で  `if iconkit.serve(self, "progress"): return`
    aiohttp:              r = iconkit.lookup("home", request.path); if r: return web.Response(body=r[0], headers=r[1])
    ページ:               iconkit.head_tags("home")  を <head> に
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:   # 型のためだけ(実行時は FastAPI / Starlette を要らない)
    from http.server import BaseHTTPRequestHandler

    from starlette.requests import Request
    from starlette.responses import Response

HERE = Path(__file__).resolve().parent
ICON_DIR = HERE / "icons"

# id: (名前, ホーム画面の短い名前, c1, c2, theme_color, background_color, PNG を作るか)
#   c1/c2 はアイコンの配色(icons.py が使う)。theme/background はページ側の暗い地に合わせる。
_T = [
    ("home",     "ホーム",          "ホーム",     "#ffb74d", "#e8590c", "#1a1a19", "#1a1a19", True),
    ("progress", "進み具合",        "進み具合",   "#4da3ff", "#3b3fd8", "#0d0d0d", "#0d0d0d", True),
    ("notes",    "メモ",            "メモ",       "#fbbf24", "#7c3aed", "#0d0d0d", "#0d0d0d", True),
    ("money",    "家計",            "家計",       "#ffd34d", "#f08a00", "#0d0d0d", "#0d0d0d", True),
    # ページ内のタイル専用(SVG だけ)
    ("monitor",  "監視",            "監視",       "#4ade80", "#166534", "#0d0d0d", "#0d0d0d", False),
    ("notify",   "通知",            "通知",       "#ffd23f", "#f06a00", "#0d0d0d", "#0d0d0d", False),
    ("approve",  "承認",            "承認",       "#a3e635", "#3f6212", "#0d0d0d", "#0d0d0d", False),
    ("book",     "ほん",            "ほん",       "#c08457", "#be4b6f", "#0d0d0d", "#0d0d0d", False),
]
META = {t[0]: dict(name=t[1], short=t[2], c1=t[3], c2=t[4], theme=t[5], bg=t[6], png=t[7]) for t in _T}

CACHE = "public, max-age=86400"

# 公開パス → (ファイル名の作り方, Content-Type)
_PUBLIC = {
    "/apple-touch-icon.png": ("{id}-180.png", "image/png"),
    "/apple-touch-icon-precomposed.png": ("{id}-180.png", "image/png"),
    "/icon-192.png": ("{id}-192.png", "image/png"),
    "/icon-512.png": ("{id}-512.png", "image/png"),
    # 新しい名前(iOS が以前の取得結果をサイト単位で覚えるので、作り直したら名前を変える。クエリ ?v= は使わない)
    "/icon-v3-180.png": ("{id}-180.png", "image/png"),
    "/icon-v3-192.png": ("{id}-192.png", "image/png"),
    "/icon-v3-512.png": ("{id}-512.png", "image/png"),
    "/favicon.svg": ("{id}.svg", "image/svg+xml"),
}
PUBLIC_PATHS = tuple(_PUBLIC) + ("/manifest.webmanifest",)

# Font Awesome(絵文字を置き換える部品)。/kit を配っていない画面にも、同じ公開パスで返す(アイコンは秘密ではない)。
#   画面側: <script src="/kit/fa.js"></script><script src="/kit/fa-emoji.js"></script>(他のスクリプトより前に)
_KIT_JS = {"/kit/fa.js": "fa.js", "/kit/fa-emoji.js": "fa-emoji.js"}
KIT_CACHE = "public, max-age=300"

_cache: dict[str, tuple[float, bytes]] = {}


def _read(name: str) -> bytes | None:
    p = ICON_DIR / name
    try:
        mt = p.stat().st_mtime
    except OSError:
        return None
    hit = _cache.get(name)
    if hit and hit[0] == mt:
        return hit[1]
    try:
        b = p.read_bytes()
    except OSError:
        return None
    _cache[name] = (mt, b)
    return b


def manifest(icon_id: str) -> bytes:
    m = META[icon_id]
    icons = []
    # iOS は SVG のアイコンを使えない。manifest に SVG(sizes any)があると、iOS がそれを選んで描けず、
    # ホーム画面がページの縮小画像になることがある → PNG だけにする(?v= は古いキャッシュを使わせないため。サーバー側は無視する)
    if m["png"]:
        icons += [{"src": "/icon-v3-180.png", "sizes": "180x180", "type": "image/png", "purpose": "any"},
                  {"src": "/icon-v3-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                  {"src": "/icon-v3-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}]
    else:
        icons.append({"src": "/favicon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"})
    obj = {"name": m["name"], "short_name": m["short"], "start_url": "/", "scope": "/", "display": "standalone",
           "theme_color": m["theme"], "background_color": m["bg"], "icons": icons}
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def lookup(icon_id: str, path: str) -> tuple[bytes, dict[str, str]] | None:
    """公開パスなら (本体 bytes, ヘッダ dict)。違う/ファイルが無いなら None。"""
    if icon_id not in META:
        return None
    path = path.split("?", 1)[0]
    if path in _KIT_JS:
        try:
            js = (HERE / _KIT_JS[path]).read_bytes()
        except OSError:
            return None
        return js, {"Content-Type": "application/javascript; charset=utf-8", "Cache-Control": KIT_CACHE}
    if path == "/manifest.webmanifest":
        return manifest(icon_id), {"Content-Type": "application/manifest+json; charset=utf-8", "Cache-Control": CACHE}
    ent = _PUBLIC.get(path)
    if not ent:
        return None
    if not META[icon_id]["png"] and ent[1] == "image/png":
        return None
    body = _read(ent[0].format(id=icon_id))
    if body is None:
        return None
    return body, {"Content-Type": ent[1], "Cache-Control": CACHE}


def response(icon_id: str, path: str, method: str = "GET") -> Response | None:
    """FastAPI/Starlette 用。公開パス(GET/HEAD)なら Response、違えば None。"""
    if method not in ("GET", "HEAD"):
        return None
    r = lookup(icon_id, path)
    if r is None:
        return None
    from starlette.responses import Response
    return Response(content=r[0], headers=r[1])


def install(app: Any, icon_id: str) -> None:
    """ゲートのない FastAPI アプリに公開パスを足す(ミドルウェア。他の処理より前に返す)。"""
    @app.middleware("http")
    async def _icons(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        r = response(icon_id, request.url.path, request.method)
        return r if r is not None else await call_next(request)


def serve(handler: BaseHTTPRequestHandler, icon_id: str) -> bool:
    """http.server 用。do_GET の先頭で呼ぶ。公開パスなら返事を書いて True。"""
    if getattr(handler, "command", "GET") not in ("GET", "HEAD"):
        return False
    r = lookup(icon_id, handler.path)
    if r is None:
        return False
    body, hdr = r
    handler.send_response(200)
    for k, v in hdr.items():
        handler.send_header(k, v)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(body)
    return True


def head_tags(icon_id: str, *, theme_color: bool = False, status_bar: str = "black-translucent") -> str:
    """<head> に入れる断片(アイコン・manifest・ホーム画面の名前など)。

    status_bar: 画面が safe-area(ノッチ・ステータスバー)に対応していないページは "black" か "default" にする。"""
    m = META[icon_id]
    t = [
        '<link rel="apple-touch-icon" sizes="180x180" href="/icon-v3-180.png">',
        '<link rel="apple-touch-icon-precomposed" sizes="180x180" href="/icon-v3-180.png">',
        '<link rel="icon" type="image/svg+xml" href="/favicon.svg">',
        '<link rel="manifest" href="/manifest.webmanifest">',
        '<meta name="apple-mobile-web-app-capable" content="yes">',
        '<meta name="mobile-web-app-capable" content="yes">',
        f'<meta name="apple-mobile-web-app-title" content="{m["short"]}">',
        f'<meta name="apple-mobile-web-app-status-bar-style" content="{status_bar}">',
    ]
    if theme_color:
        t.append(f'<meta name="theme-color" content="{m["theme"]}">')
    return "\n".join(t) + "\n"
