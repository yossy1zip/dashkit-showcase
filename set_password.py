#!/usr/bin/env python3
"""合言葉のハッシュを、指定したデータ領域の gate.json に書く(値は表示しない・引数にも取らない)。

  read -rs PW && printf '%s' "$PW" | python3 set_password.py /srv/myapp-data [所有者ユーザー名]; unset PW
  python3 set_password.py /srv/myapp-data          # 端末なら、その場で入力を求める(画面に出ない)

合言葉は標準入力から読む(シェルの履歴やプロセス一覧に残さないため)。
書いた gate.json は 600。所有者を指定すると chown する(root で動かすとき)。
"""
import getpass
import os
import pwd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    data_dir = Path(sys.argv[1])
    owner = sys.argv[2] if len(sys.argv) > 2 else None
    pw = getpass.getpass("合言葉: ") if sys.stdin.isatty() else sys.stdin.read().rstrip("\n")
    if len(pw) < 4:
        sys.exit("合言葉が短すぎます(4文字以上)")
    gate.set_password(data_dir, pw)
    if owner:
        u = pwd.getpwnam(owner)
        os.chown(gate.gate_path(data_dir), u.pw_uid, u.pw_gid)
    print("ok:", gate.gate_path(data_dir))


if __name__ == "__main__":
    main()
