"""ダッシュボード共通のログイン(合言葉)ゲート。標準ライブラリ+FastAPI。

- 合言葉の値はコードにも設定にも書かない。ハッシュ(PBKDF2)だけをデータ領域の gate.json(600)に置く。
  設定は `python3 set_password.py <データ領域>`(標準入力から読む)。
- gate.json が無いときは**閉じる**(合言葉が未設定、と表示。何も見せない)。
- 通ったら署名つき cookie(既定 180 日)。連続で間違えると5分ロック(リバースプロキシ経由では送信元が同じに見えるので、全体で数える)。
- 書き込み系(POST/PUT/DELETE)は X-Requested-With: <name> を必須にする(別サイトのページから勝手に書かせない)。
- **合言葉なしにする**: データ領域に `gate-open` というファイルがあると、ログインを求めない(VPN の中だけで開く前提)。
  書き込みの X-Requested-With の確認は残す。元に戻すには、このファイルを消すだけ(gate.json はそのまま残してある)。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

ITER = 200_000
OPEN_FLAG = "gate-open"      # データ領域にこのファイルがあれば、合言葉を求めない
MAX_AGE = 180 * 86400
LOCK_FAILS = 8               # LOCK_WINDOW 秒の間にこの回数まちがえたらロック
LOCK_WINDOW = 300
_fails: list[float] = []

LOGIN_HTML = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#0d0d0d">
<title>__TITLE__</title><style>
html,body{height:100%;margin:0;background:#0d0d0d;color:#fff;font:15px/1.7 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP","Noto Sans CJK JP",system-ui,sans-serif}
main{min-height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;padding:24px}
h1{font-size:15px;font-weight:600;letter-spacing:.12em;margin:0}
p{margin:0;color:#898781;font-size:12.5px;text-align:center}
form{display:flex;gap:8px;width:min(320px,100%)}
input{flex:1;min-width:0;height:46px;border-radius:12px;border:1px solid #383835;background:#1a1a19;color:#fff;padding:0 14px;font:inherit}
button{height:46px;padding:0 18px;border-radius:12px;border:0;background:#3987e5;color:#fff;font:inherit;font-weight:600}
#msg{min-height:1.4em;color:#ec835a}
</style></head><body><main>
<h1>__TITLE__</h1><p>__NOTE__</p>
<form id="f"><input id="pw" type="password" autocomplete="current-password" placeholder="合言葉" autofocus><button>入る</button></form>
<p id="msg"></p></main>
<script>
document.getElementById('f').addEventListener('submit',async e=>{e.preventDefault();
 const m=document.getElementById('msg');m.textContent='';
 const r=await fetch('/login',{method:'POST',headers:{'X-Requested-With':'__HDR__','Content-Type':'application/json'},body:JSON.stringify({password:document.getElementById('pw').value})});
 if(r.ok){location.replace(location.pathname+location.search+location.hash)}else{m.textContent=r.status===429?'しばらくしてからもう一度':'合言葉が違います'}});
</script></body></html>"""

UNSET_HTML = """<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<body style="background:#0d0d0d;color:#c3c2b7;font:15px/1.8 system-ui,sans-serif;padding:40px 24px"><h1 style="font-size:16px;color:#fff">合言葉が未設定です(または設定ファイルが読めません)</h1>
<p>サーバーで <code>python3 set_password.py &lt;データ領域&gt;</code> を実行してください。</p></body></html>"""


def gate_path(data_dir: Path) -> Path:
    return Path(data_dir) / "gate.json"


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITER).hex()


def set_password(data_dir: Path, password: str) -> None:
    """ハッシュを書く。cookie 署名用の秘密も作り直す(=既存のログインは全部切れる)。"""
    d = Path(data_dir)
    d.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_bytes(16)
    obj = {"v": 1, "salt": salt.hex(), "hash": _hash(password, salt), "secret": secrets.token_hex(32)}
    p = gate_path(d)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, p)


def _load(data_dir: Path) -> dict[str, Any] | None:
    """gate.json を読む。無い・壊れている・形が違うときは None(=閉じる)。"""
    try:
        g = json.loads(gate_path(data_dir).read_text())
        if not isinstance(g, dict) or not all(isinstance(g.get(k), str) and g[k] for k in ("salt", "hash", "secret")):
            return None
        bytes.fromhex(g["salt"])
    except (OSError, ValueError):
        return None
    return g


def _sign(secret: str, exp: int) -> str:
    return hmac.new(secret.encode(), str(exp).encode(), hashlib.sha256).hexdigest()


def _valid_cookie(secret: str, value: str | None) -> bool:
    if not value or "." not in value:
        return False
    exp_s, sig = value.split(".", 1)
    try:
        exp = int(exp_s)
    except ValueError:
        return False
    # bytes で比べる(str の compare_digest は ASCII 以外が来ると例外になる。cookie は外から来る値)
    return exp > time.time() and hmac.compare_digest(sig.encode(), _sign(secret, exp).encode())


def install(app: FastAPI, data_dir_fn: Callable[[], Path | str], *, cookie: str, title: str, header: str,
            note: str = "VPN の中だけで開けます", icon: str | None = None) -> None:
    """app にゲートを入れる。data_dir_fn() はデータ領域の Path(テストで差し替えられるよう関数で受ける)。

    icon に iconkit のアイコン id を渡すと、認証より前に公開パス(/apple-touch-icon.png /icon-192.png /icon-512.png /favicon.svg
    /manifest.webmanifest)を返し、ログイン画面の <head> にも入れる(ホーム画面に追加したときアイコンが出るように)。
    """
    login_html = LOGIN_HTML
    if icon:
        import iconkit
        login_html = LOGIN_HTML.replace("<title>", iconkit.head_tags(icon) + "<title>", 1)

    @app.middleware("http")
    async def _gate(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        path = request.url.path
        if icon:
            r = iconkit.response(icon, path, request.method)
            if r is not None:
                return r
        if (Path(data_dir_fn()) / OPEN_FLAG).exists():             # 合言葉なし(書き込みの確認ヘッダーだけは残す)
            if path == "/login" and request.method == "GET":
                return RedirectResponse("/")
            if request.method not in ("GET", "HEAD") and request.headers.get("x-requested-with") != header:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            if path in ("/login", "/logout") and request.method == "POST":
                return JSONResponse({"ok": True})
            resp = await call_next(request)
            resp.headers["Cache-Control"] = "no-store" if path.startswith("/api/") else "no-cache"
            resp.headers["X-Robots-Tag"] = "noindex"
            return resp
        g = _load(Path(data_dir_fn()))
        if g is None:
            return HTMLResponse(UNSET_HTML, status_code=503)
        if path == "/login" and request.method == "GET":
            return HTMLResponse(login_html.replace("__TITLE__", title).replace("__NOTE__", note).replace("__HDR__", header))
        if request.method not in ("GET", "HEAD") and request.headers.get("x-requested-with") != header:
            return JSONResponse({"error": "forbidden"}, status_code=403)
        if path == "/login" and request.method == "POST":
            now = time.time()
            _fails[:] = [t for t in _fails if now - t < LOCK_WINDOW]
            if len(_fails) >= LOCK_FAILS:
                return JSONResponse({"error": "locked"}, status_code=429)
            try:
                body = await request.json()
                pw = str(body.get("password", ""))
            except Exception:
                pw = ""
            if not hmac.compare_digest(_hash(pw, bytes.fromhex(g["salt"])), g["hash"]):
                _fails.append(now)
                return JSONResponse({"error": "bad"}, status_code=401)
            exp = int(now) + MAX_AGE
            resp = JSONResponse({"ok": True})
            secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
            resp.set_cookie(cookie, f"{exp}.{_sign(g['secret'], exp)}", max_age=MAX_AGE, httponly=True, samesite="lax", secure=secure, path="/")
            return resp
        if path == "/logout" and request.method == "POST":
            resp = JSONResponse({"ok": True})
            resp.delete_cookie(cookie, path="/")
            return resp
        if not _valid_cookie(g["secret"], request.cookies.get(cookie)):
            if path.startswith("/api/"):
                return JSONResponse({"error": "login"}, status_code=401)
            return HTMLResponse(login_html.replace("__TITLE__", title).replace("__NOTE__", note).replace("__HDR__", header))
        resp = await call_next(request)
        resp.headers["Cache-Control"] = "no-store" if path.startswith("/api/") else "no-cache"
        resp.headers["X-Robots-Tag"] = "noindex"
        return resp
