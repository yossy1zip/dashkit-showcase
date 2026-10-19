#!/usr/bin/env python3
"""秘密・個人情報・内部の住所が git に入っていないかの自己点検(標準ライブラリだけ)。

  python3 -I scripts/scan_private.py            # git が追跡しているファイルを見る。見つかったら 1 で終わる
  python3 -I scripts/scan_private.py FILE...     # 指定したファイルだけ

見るもの: 秘密鍵・よくあるトークンの形・127.0.0.1 以外の IPv4・example.com / noreply 以外のメール・
/mnt /opt /home /Users /root のパス・.local .lan .internal .home.arpa .ts.net の名前。
gitleaks の代わりではない(持ち主の側では gitleaks も回す)。ここは「うっかり」を早く見つけるための軽い網。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 第三者のファイル(Font Awesome の元データ・ライセンス文)と、この点検そのもの・その試験は見ない
SKIP = {"fa.js", "fa-LICENSE.txt", "scripts/scan_private.py", "tests/test_scan_private.py"}
SKIP_SUFFIX = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2")

ALLOWED_IPS = {"127.0.0.1", "0.0.0.0"}  # noqa: S104  (待ち受けではなく、点検で許す文字列)
ALLOWED_MAIL = re.compile(r"@(example\.(com|org|net)|users\.noreply\.github\.com|anthropic\.com)$", re.I)

RULES: list[tuple[str, re.Pattern[str]]] = [
    ("秘密鍵", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("トークンの形", re.compile(r"\b(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gh[ousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[abpr]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9_-]{20,})")),
    ("IPv4", re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")),
    ("メール", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("内部のパス", re.compile(r"(?<![\w.])/(mnt|opt|home|Users|root)/[\w.-]+")),
    ("内部の名前", re.compile(r"\b[\w-]+\.(local|lan|internal|home\.arpa|ts\.net)\b", re.I)),
]


def allowed(kind: str, text: str) -> bool:
    if kind == "IPv4":
        parts = text.split(".")
        return text in ALLOWED_IPS or any(int(p) > 255 for p in parts)   # 255 を超えるのは版番号などで IP ではない
    if kind == "メール":
        return bool(ALLOWED_MAIL.search(text))
    return False


def scan_text(text: str) -> list[tuple[int, str, str]]:
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        for kind, rx in RULES:
            for m in rx.finditer(line):
                if not allowed(kind, m.group(0)):
                    found.append((n, kind, m.group(0)))
    return found


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout  # noqa: S603, S607
    return [p for p in out.decode().split("\0") if p]


def main(argv: list[str]) -> int:
    files = argv or tracked()
    bad = 0
    for rel in files:
        if rel in SKIP or rel.lower().endswith(SKIP_SUFFIX):
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for n, kind, hit in scan_text(text):
            # 見つけた値そのものは途中まで(ログに秘密を全部出さない)
            print(f"{rel}:{n}: {kind}: {hit[:6]}…")
            bad += 1
    print(f"scan_private: {len(files)} files, {bad} findings")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
