#!/usr/bin/env python3
"""Font Awesome Free のアイコン(一部)を、外へのリクエストなしで使えるよう `fa.js` にまとめる。

  python3 -I fa_build.py <FA の svgs ディレクトリ(…/fontawesomefree/static/fontawesomefree/svgs)> [--license <LICENSE.txt>]

- 元のファイルは「信頼できないデータ」として扱う: 読むのは SVG の viewBox と <path d="…"> だけ(正規表現)。実行はしない。
  d に使える文字・viewBox の形を検査して、合わなければ止まる。
- 使うアイコンは下の ICONS に足す(名前は FA の名前。solid は "name"、regular は "r:name")。足したら、このスクリプトを流し直す。
- ライセンス: アイコン = CC BY 4.0(表示が必要)。`fa.js` の先頭と `fa-LICENSE.txt` に載せる。
  入手元: PyPI の fontawesomefree 6.6.0(pip download fontawesomefree --no-deps)を、空のディレクトリに展開して使った。
- 使い方(画面): `<script src="/kit/fa.js">` のあと、`fa('house')` が <svg class="fa"> の文字列を返す。色は currentColor、大きさは 1em(CSS で font-size を変える)。
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = "6.6.0"
ICONS = [
    # つぶやき・やりとり
    "comment", "comments", "comment-dots", "reply", "pen", "pen-to-square", "trash", "paper-plane", "quote-left", "hashtag", "feather", "feather-pointed",
    # しるし
    "bookmark", "r:bookmark", "star", "r:star", "heart", "r:heart", "lightbulb", "fire", "bolt", "check", "xmark", "circle-check", "lock", "eye", "eye-slash",
    # 声(AI・ノリ友・辛口・参謀)
    "robot", "face-smile-wink", "pepper-hot", "chess-knight", "user-group", "wand-magic-sparkles", "brain",
    # 画面・操作
    "house", "book", "book-open", "moon", "calendar-days", "chart-line", "gear", "sliders", "ellipsis", "chevron-down", "chevron-up", "chevron-right",
    "rotate", "arrow-rotate-right", "folder-open", "file-import", "file-export", "plus", "bars", "share-nodes", "cloud-moon", "note-sticky", "feather",
    "arrow-up-right-from-square", "magnifying-glass", "filter", "clock", "tags", "circle-info", "triangle-exclamation", "spinner", "broom", "recycle", "calendar-check", "bullhorn",
]
PATH_OK = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9eE.,\-+ \n]+$")
BOX_OK = re.compile(r"^0 0 \d{2,4} \d{2,4}$")


def map_names() -> list[str]:
    """fa-emoji.js の対応表(MAP-BEGIN〜MAP-END)で使っているアイコン名。fa.js に必ず入れる。"""
    src = (HERE / "fa-emoji.js").read_text(encoding="utf-8")
    blk = src.split("/*MAP-BEGIN*/", 1)[1].split("/*MAP-END*/", 1)[0]
    return re.findall(r"\[\s*'((?:r:)?[a-z0-9-]+)'", blk)


def load(svgs: Path, name: str) -> tuple[int, int, str]:
    style, n = ("regular", name[2:]) if name.startswith("r:") else ("solid", name)
    p = svgs / style / f"{n}.svg"
    raw = p.read_text(encoding="utf-8")
    m = re.search(r'viewBox="([^"]+)"', raw)
    d = re.findall(r'<path[^>]*\sd="([^"]+)"', raw)
    if not m or not BOX_OK.match(m.group(1)) or len(d) != 1 or not PATH_OK.match(d[0]):
        raise SystemExit(f"想定外の形のアイコンです: {name}")
    w, h = m.group(1).split()[2:]
    return int(w), int(h), re.sub(r"\s+", " ", d[0]).strip()


def main() -> None:
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    svgs = Path(args[0])
    out = []
    seen = set()
    for n in ICONS + map_names():
        if n in seen:
            continue
        seen.add(n)
        w, h, d = load(svgs, n)
        out.append(f"  '{n}':[{w},{h},'{d}']")
    js = f"""/* Font Awesome Free {VERSION} のアイコン(一部)。Icons: CC BY 4.0 License (https://fontawesome.com/license/free)。Copyright Fonticons, Inc.
   外のサーバーからは何も読み込まない。作り方は fa_build.py。使い方: fa('house') → <svg class="fa"> の文字列(色は currentColor・大きさは 1em)。
   r: 付きは regular(線)、なしは solid(塗り)。 */
(function (g) {{
  const FA = {{
{(","+chr(10)).join(out)}
  }};
  g.FA = FA;
  g.fa = function (name, cls) {{
    const x = FA[name];
    if (!x) return '';
    return '<svg class="fa fa-' + name.replace(':', '-') + (cls ? ' ' + cls : '') + '" viewBox="0 0 ' + x[0] + ' ' + x[1] + '" aria-hidden="true" focusable="false"><path fill="currentColor" d="' + x[2] + '"/></svg>';
  }};
}})(window);
"""
    (HERE / "fa.js").write_text(js, encoding="utf-8")
    if "--license" in args:
        lic = Path(args[args.index("--license") + 1]).read_text(encoding="utf-8")
        (HERE / "fa-LICENSE.txt").write_text(f"Font Awesome Free {VERSION}（入手元: PyPI fontawesomefree）\nアイコンは CC BY 4.0。以下は同梱のライセンス全文。\n\n" + lic, encoding="utf-8")
    print(f"wrote fa.js ({len(out)} icons, {len(js)} bytes)")


if __name__ == "__main__":
    main()
