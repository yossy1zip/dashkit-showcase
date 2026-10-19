#!/usr/bin/env python3
"""README のスクリーンショット(docs/*.png)を作り直す。標準ライブラリだけ + 手元の Chromium。

  CHROME=/path/to/chrome python3 -I demo/screenshots.py      # fastapi が要る(gate.py のログイン画面を使うため)

- 写すのは demo/index.html(合成データ)と gate.py のログイン画面だけ。サーバーは立てない・ネットワークも使わない。
- headless の Chromium は窓の幅を 500px より狭くできないので、スマホ幅(390px)は iframe に入れて写す。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import gate  # noqa: E402

DOCS = ROOT / "docs"
WORK = ROOT / "out" / "screenshots"   # .gitignore 済み


def chrome() -> str:
    c = os.environ.get("CHROME") or shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("chrome")
    if not c:
        raise SystemExit("Chromium が見つかりません。CHROME=<実行ファイル> を指定してください")
    return c


def shot(src: Path, out: Path, width: int, height: int, scale: int = 1) -> None:
    subprocess.run([chrome(), "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",  # noqa: S603
                    f"--force-device-scale-factor={scale}", f"--window-size={width},{height}", "--virtual-time-budget=3000",
                    f"--screenshot={out}", src.resolve().as_uri()], check=True, capture_output=True, timeout=120)
    print("wrote", out.relative_to(ROOT))


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    demo = ROOT / "demo" / "index.html"
    shot(demo, DOCS / "demo.png", 1280, 1200)
    frame = WORK / "mobile.html"
    frame.write_text(f'<!doctype html><body style="margin:0;background:#0d0d0d"><iframe src="{demo.resolve().as_uri()}" '
                     'style="border:0;width:390px;height:2300px;display:block"></iframe></body>', encoding="utf-8")
    shot(frame, DOCS / "demo-mobile.png", 390, 2300, scale=2)
    login = WORK / "login.html"
    login.write_text(gate.LOGIN_HTML.replace("__TITLE__", "EXAMPLE").replace("__NOTE__", "VPN の中だけで開けます")
                     .replace("__HDR__", "example"), encoding="utf-8")
    shot(login, DOCS / "login.png", 640, 420, scale=2)


if __name__ == "__main__":
    main()
