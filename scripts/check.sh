#!/bin/sh
# 点検(lint・型・秘密・試験)を手元で全部回す。どれか1つでも落ちたら止まる(終了コード 1)。
#   pip install -r requirements-dev.txt && sh scripts/check.sh
set -eu
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}

echo "== ruff (lint・セキュリティ規則)";  "$PY" -m ruff check .
echo "== mypy (型)";                      "$PY" -m mypy
echo "== 秘密・内部の住所の点検";         "$PY" -I scripts/scan_private.py
echo "== 試験";                           "$PY" -m unittest discover -s tests
echo "OK: すべて通りました"
