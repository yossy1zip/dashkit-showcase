#!/usr/bin/env python3
"""アイコン生成器。全部の SVG を定義して `dashkit/icons/` に書き出す。作り直しは `python3 icons.py` だけ。

  python3 icons.py            # SVG(角丸タイル) と PNG(180/192/512・角丸なしの全面塗り・透過なし) を全部作り直す
  python3 icons.py --sheet    # さらに確認用コンタクトシート out/icons-work/sheet.png も作る(out/ は git に入れない)
  python3 icons.py --only money,notes   # 一部だけ

PNG とシートの描画には playwright(Chromium)が要る。無ければ SVG だけ作る。
環境変数 ICONS_PW_PYTHON に playwright 入りの python を指定すると、そちらで再実行する。

デザインの約束(統一感):
  512x512。背景=斜めの線形グラデ(左上 c1 → 右下 c2)+左上からの白い放射グラデ(.20→0)。枠線なし。
  図形は白が主役、線の太さ 30〜36・丸い線端/結合、中央に全体の約55〜62%。副要素は白の60%か1色のアクセント。
  ごく軽い影(feGaussianBlur で下へ8px・黒.25)。文字・絵文字は使わない(図形だけ)。
"""
from __future__ import annotations

import base64
import math
import os
import re
import struct
import subprocess
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import iconkit  # noqa: E402  (META: 名前・配色)

OUT = HERE / "icons"
WORK = HERE / "out" / "icons-work"   # 共有の /tmp ではなくリポジトリの中(.gitignore 済み)
PW_PY = os.environ.get("ICONS_PW_PYTHON")   # playwright が入った別の python を使うとき(任意)

W = "#fff"
SW = 32  # 標準の線の太さ


# ------------------------------------------------------------------ 部品
def n(x: float) -> str:
    s = f"{x:.1f}"
    return s[:-2] if s.endswith(".0") else s


def stroke(d: str, w: float = SW, op: float = 1, extra: str = "") -> str:
    o = f' opacity="{op}"' if op != 1 else ""
    return f'<path d="{d}" fill="none" stroke="{W}" stroke-width="{n(w)}" stroke-linecap="round" stroke-linejoin="round"{o}{extra}/>'


def fillp(d: str, op: float = 1, soft: float = 0, extra: str = "") -> str:
    """白で塗る。soft>0 のときは同じ白の縁線で角を丸める。"""
    o = f' opacity="{op}"' if op != 1 else ""
    s = f' stroke="{W}" stroke-width="{n(soft)}" stroke-linejoin="round"' if soft else ""
    return f'<path d="{d}" fill="{W}"{s}{o}{extra}/>'


def rrect(x, y, w, h, r, op: float = 1, mode: str = "fill", sw: float = SW, extra: str = "") -> str:
    o = f' opacity="{op}"' if op != 1 else ""
    if mode == "fill":
        return f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="{n(r)}" fill="{W}"{o}{extra}/>'
    return (f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="{n(r)}" fill="none" stroke="{W}" '
            f'stroke-width="{n(sw)}" stroke-linejoin="round"{o}{extra}/>')


def circle(cx, cy, r, op: float = 1, mode: str = "fill", sw: float = SW, extra: str = "") -> str:
    o = f' opacity="{op}"' if op != 1 else ""
    if mode == "fill":
        return f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="{W}"{o}{extra}/>'
    return f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="none" stroke="{W}" stroke-width="{n(sw)}"{o}{extra}/>'


def star_d(cx, cy, R, a: float = 0.17) -> str:
    """4点のきらめきのパス(辺がへこんだ星)。"""
    c = R * a
    return (f"M{n(cx)} {n(cy - R)} Q{n(cx + c)} {n(cy - c)} {n(cx + R)} {n(cy)} Q{n(cx + c)} {n(cy + c)} {n(cx)} {n(cy + R)} "
            f"Q{n(cx - c)} {n(cy + c)} {n(cx - R)} {n(cy)} Q{n(cx - c)} {n(cy - c)} {n(cx)} {n(cy - R)} Z")


def star4(cx, cy, R, op: float = 1, a: float = 0.17, soft: float = 6) -> str:
    """4点のきらめき(辺がへこんだ星)。"""
    return fillp(star_d(cx, cy, R, a), op, soft)


def polar(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def arrow_arc(cx, cy, r, a_s, a_e, w=24, head=26):
    """a_s から a_e(度・時計回り)までの円弧+終点の矢じり。"""
    p0 = polar(cx, cy, r, a_s)
    pe = polar(cx, cy, r, a_e)
    ar = math.radians(a_e)
    tx, ty = -math.sin(ar), math.cos(ar)
    nx, ny = math.cos(ar), math.sin(ar)
    tip = (pe[0] + head * 1.1 * tx, pe[1] + head * 1.1 * ty)
    b1 = (pe[0] - head * 0.3 * tx + head * nx, pe[1] - head * 0.3 * ty + head * ny)
    b2 = (pe[0] - head * 0.3 * tx - head * nx, pe[1] - head * 0.3 * ty - head * ny)
    big = 1 if (a_e - a_s) % 360 > 180 else 0
    return (stroke(f"M{n(p0[0])} {n(p0[1])} A{n(r)} {n(r)} 0 {big} 1 {n(pe[0])} {n(pe[1])}", w)
            + fillp(f"M{n(tip[0])} {n(tip[1])} L{n(b1[0])} {n(b1[1])} L{n(b2[0])} {n(b2[1])} Z", soft=8))


def sh(u: str, body: str) -> str:
    """影つきのグループ。"""
    return f'<g filter="url(#sh-{u})">{body}</g>'


def ko(u: str, d: str, sw: float = 0) -> str:
    """「背景色で抜く」。背景グラデ+ハイライトを userSpaceOnUse で重ねるので、継ぎ目なく図形を切り抜いたように見える。"""
    if sw:
        a = f'fill="none" stroke-width="{n(sw)}" stroke-linecap="round" stroke-linejoin="round" stroke'
        return f'<path d="{d}" {a}="url(#bg-{u})"/><path d="{d}" {a}="url(#hl-{u})"/>'
    return f'<path d="{d}" fill="url(#bg-{u})"/><path d="{d}" fill="url(#hl-{u})"/>'


def ko_circle(u: str, cx, cy, r) -> str:
    return (f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="url(#bg-{u})"/>'
            f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="url(#hl-{u})"/>')


def crescent(cx, cy, R, ix, iy, r) -> str:
    """外円(cx,cy,R)から内円(ix,iy,r)を抜いた三日月のパス。"""
    dx, dy = ix - cx, iy - cy
    d = math.hypot(dx, dy)
    a = (R * R - r * r + d * d) / (2 * d)
    h = math.sqrt(R * R - a * a)
    mx, my = cx + a * dx / d, cy + a * dy / d
    p1 = (mx + h * dy / d, my - h * dx / d)
    p2 = (mx - h * dy / d, my + h * dx / d)

    def ang(c, p):
        return math.atan2(p[1] - c[1], p[0] - c[0])

    def arc(c, rad, p_from, p_to, via):
        t0, t1, tv = ang(c, p_from), ang(c, p_to), ang(c, via)
        two = 2 * math.pi
        span_cw = (t1 - t0) % two
        via_cw = (tv - t0) % two
        if via_cw <= span_cw:      # 時計回り(sweep=1)で via を通る
            sweep, span = 1, span_cw
        else:
            sweep, span = 0, two - span_cw
        large = 1 if span > math.pi else 0
        return f"A{n(rad)} {n(rad)} 0 {large} {sweep} {n(p_to[0])} {n(p_to[1])}"

    far = (cx - R * dx / d, cy - R * dy / d)         # 外円の、内円から一番遠い点
    near = (ix - r * dx / d, iy - r * dy / d)
    return f"M{n(p1[0])} {n(p1[1])} " + arc((cx, cy), R, p1, p2, far) + " " + arc((ix, iy), r, p2, p1, near) + " Z"


# ------------------------------------------------------------------ 共通の外枠
BRAND_DIR = HERE / "brand"     # 第三者サービスの公式ロゴを載せるときの置き場(このリポジトリには入れていない)
BRAND: dict = {}   # id: (ファイル, 余白の割合, タイルの色 上, 下)


def _mix(a: str, b: str, k: float = 0.5) -> str:
    """2色の中間色(#rrggbb)。"""
    ra, ga, ba = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
    rb, gb, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
    return f"#{round(ra + (rb - ra) * k):02x}{round(ga + (gb - ga) * k):02x}{round(ba + (bb - ba) * k):02x}"


def _tile_defs(u: str, c1: str, c2: str) -> str:
    """ツヤのあるタイル: 縦のグラデ(上が明るい)+上からの光+下の影+縁の内側のハイライト。"""
    return (
        "<defs>\n"
        f'<linearGradient id="bg-{u}" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="120" y2="512">'
        f'<stop offset="0" stop-color="{c1}"/><stop offset=".55" stop-color="{_mix(c1, c2, 0.5)}"/><stop offset="1" stop-color="{c2}"/></linearGradient>\n'
        f'<linearGradient id="gl-{u}" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="512">'
        '<stop offset="0" stop-color="#fff" stop-opacity=".40"/><stop offset=".30" stop-color="#fff" stop-opacity=".12"/>'
        '<stop offset=".55" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".16"/></linearGradient>\n'
        f'<radialGradient id="hl-{u}" gradientUnits="userSpaceOnUse" cx="150" cy="-40" r="420">'
        '<stop offset="0" stop-color="#fff" stop-opacity=".38"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>\n'
        f'<filter id="sh-{u}" x="-25%" y="-25%" width="150%" height="150%" color-interpolation-filters="sRGB">'
        '<feGaussianBlur in="SourceAlpha" stdDeviation="8"/><feOffset dy="8" result="b"/>'
        '<feColorMatrix in="b" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .28 0" result="s"/>'
        '<feMerge><feMergeNode in="s"/><feMergeNode in="SourceGraphic"/></feMerge></filter>\n'
        "</defs>\n"
    )


def _tile_body(u: str, rx: str) -> str:
    return (
        f'<rect width="512" height="512"{rx} fill="url(#bg-{u})"/>\n'
        f'<rect width="512" height="512"{rx} fill="url(#hl-{u})"/>\n'
        f'<rect width="512" height="512"{rx} fill="url(#gl-{u})"/>\n'
    )


def _tile_edge(rx: str) -> str:
    # 縁の内側に細いハイライト(角丸タイルのときだけ。PNG=全面塗りでは不要)
    return '<rect x="3" y="3" width="506" height="506" rx="109" fill="none" stroke="#fff" stroke-opacity=".22" stroke-width="4"/>\n' if rx else ""


def brand_svg(icon_id: str, *, tile: bool) -> str:
    f, pad, c1, c2 = BRAND[icon_id]
    raw = (BRAND_DIR / f).read_bytes()
    mime = "image/svg+xml" if f.endswith(".svg") else "image/png"
    uri = f"data:{mime};base64," + base64.b64encode(raw).decode()
    rx = ' rx="112"' if tile else ""
    u = icon_id
    s = 512 * (1 - 2 * pad)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 512 512" width="512" height="512">\n'
        + _tile_defs(u, c1, c2) + _tile_body(u, rx)
        + f'<image href="{uri}" xlink:href="{uri}" x="{512 * pad:.0f}" y="{512 * pad:.0f}" width="{s:.0f}" height="{s:.0f}" preserveAspectRatio="xMidYMid meet"/>\n'
        + _tile_edge(rx) + "</svg>\n"
    )


def build_svg(icon_id: str, *, tile: bool) -> str:
    if icon_id in BRAND and (BRAND_DIR / BRAND[icon_id][0]).exists():
        return brand_svg(icon_id, tile=tile)
    m = iconkit.META[icon_id]
    u = icon_id
    rx = ' rx="112"' if tile else ""
    glyph = GLYPHS[icon_id](u)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">\n'
        + _tile_defs(u, m["c1"], m["c2"]) + _tile_body(u, rx) + f"{glyph}\n" + _tile_edge(rx) + "</svg>\n"
    )


# ------------------------------------------------------------------ 図形(id ごと)
def g_home(u):
    roof = stroke("M92 270 L256 128 L420 270", 34)
    walls = stroke("M146 240 V374 Q146 408 180 408 H332 Q366 408 366 374 V240", 34)
    tiles = "".join(rrect(x, y, 46, 46, 13, 0.6) for x in (201, 265) for y in (270, 332))
    return sh(u, roof + walls + tiles)


def g_progress(u):
    cx, cy, r = 256, 262, 124
    a0, sweep = -18, 296
    a1 = a0 + sweep
    p0 = polar(cx, cy, r, a0)
    # 矢じり(終点の接線方向へ)
    ae = a1 - 14
    pe = polar(cx, cy, r, ae)
    tx, ty = -math.sin(math.radians(ae)), math.cos(math.radians(ae))   # 時計回りの進行方向
    nx, ny = math.cos(math.radians(ae)), math.sin(math.radians(ae))
    tip = (pe[0] + 48 * tx, pe[1] + 48 * ty)
    b1 = (pe[0] - 4 * tx + 44 * nx, pe[1] - 4 * ty + 44 * ny)
    b2 = (pe[0] - 4 * tx - 44 * nx, pe[1] - 4 * ty - 44 * ny)
    arc_end = polar(cx, cy, r, ae - 3)
    ring = stroke(f"M{n(p0[0])} {n(p0[1])} A{r} {r} 0 1 1 {n(arc_end[0])} {n(arc_end[1])}", 34)
    head = fillp(f"M{n(tip[0])} {n(tip[1])} L{n(b1[0])} {n(b1[1])} L{n(b2[0])} {n(b2[1])} Z", soft=12)
    play = fillp("M232 222 L232 302 L304 262 Z", soft=14)
    return sh(u, ring + head + play)


def g_notes(u):
    """メモ: メモの紙(3行)と、思い出したときのきらめき。"""
    paper = rrect(132, 150, 220, 262, 30, 1, "stroke", 30)
    lines = stroke("M178 230 H306", 28) + stroke("M178 290 H306", 28) + stroke("M178 350 H254", 28, 0.6)
    return sh(u, paper + lines + star4(372, 146, 70))


def g_money(u):
    ring = circle(256, 256, 146, mode="stroke", sw=34)
    yen = (stroke("M194 182 L256 266 L318 182", 32) + stroke("M256 266 V350", 32)
           + stroke("M204 292 H308", 24) + stroke("M204 328 H308", 24))
    return sh(u, ring + yen)


def fa_path(name: str) -> str:
    """Font Awesome Free(fa.js。CC BY 4.0)のアイコンのパス。viewBox 512 のものだけ。"""
    m = re.search(r"'" + re.escape(name) + r"':\[512,512,'([^']+)'\]", (HERE / "fa.js").read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"fa.js に {name} がありません")
    return m.group(1)


# ---- ページ内タイル専用 ----
def g_monitor(u):
    wave = stroke("M88 272 H170 L208 168 L262 366 L312 214 L338 272 H424", 34)
    return sh(u, wave)


def g_notify(u):
    bell = fillp("M140 336 C176 304 184 270 184 226 C184 172 214 140 256 140 C298 140 328 172 328 226 C328 270 336 304 372 336 Z", soft=22)
    knob = circle(256, 118, 20)
    clap = fillp("M214 372 A42 42 0 0 0 298 372 Z", soft=8)
    return sh(u, knob + bell + clap)


def g_approve(u):
    doc = stroke("M174 112 H292 L372 192 V392 Q372 420 344 420 H178 Q150 420 150 392 V136 Q150 112 174 112 Z", 32)
    fold = stroke("M292 112 V192 H372", 30, 0.6)
    chk = stroke("M200 308 L240 348 L318 262", 36)
    return sh(u, doc + fold + chk)


def g_book(u):
    left = fillp("M244 150 C204 114 150 104 96 118 V366 C152 352 206 362 244 398 Z", soft=14)
    right = fillp("M268 150 C308 114 362 104 416 118 V366 C360 352 306 362 268 398 Z", 0.62, soft=14)
    lines = ""
    for dy in (0, 46, 92):
        lines += ko(u, f"M140 {196 + dy} C164 {190 + dy} 190 {194 + dy} 208 {204 + dy}", 14)
        lines += ko(u, f"M304 {204 + dy} C322 {194 + dy} 348 {190 + dy} 372 {196 + dy}", 14)
    return sh(u, left + right) + lines


GLYPHS = {k[2:]: v for k, v in list(globals().items()) if k.startswith("g_")}


# ------------------------------------------------------------------ PNG
def strip_alpha(png: bytes) -> bytes:
    """RGBA の PNG を RGB に(透過なしを保証)。標準ライブラリだけ。"""
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PNG ではありません")
    pos, idat, ihdr = 8, b"", None
    while pos < len(png):
        ln = struct.unpack(">I", png[pos:pos + 4])[0]
        tag = png[pos + 4:pos + 8]
        data = png[pos + 8:pos + 8 + ln]
        if tag == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", data)
        elif tag == b"IDAT":
            idat += data
        pos += 12 + ln
    if ihdr is None:
        raise ValueError("IHDR がありません")
    w, h, depth, ctype = ihdr[0], ihdr[1], ihdr[2], ihdr[3]
    if ctype == 2:
        return png
    if not (depth == 8 and ctype == 6):
        raise ValueError(f"想定外の PNG の形です: depth={depth} ctype={ctype}")
    bpp = 4
    raw = zlib.decompress(idat)
    stride = w * bpp
    prev = bytearray(stride)
    rows = []
    p = 0
    for _ in range(h):
        ft = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if ft == 1:
                line[i] = (line[i] + a) & 255
            elif ft == 2:
                line[i] = (line[i] + b) & 255
            elif ft == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif ft == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        prev = line
        rows.append(line)
    out = bytearray()
    for line in rows:
        out.append(0)
        for i in range(0, stride, 4):
            out += line[i:i + 3]

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(out), 9)) + chunk(b"IEND", b""))


def data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


# ------------------------------------------------------------------ playwright 側
def render_all(only: list[str], sheet: bool) -> None:
    from playwright.sync_api import sync_playwright
    OUT.mkdir(exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    ids = [i for i in iconkit.META if not only or i in only]
    with sync_playwright() as p:
        b = p.chromium.launch()
        for i in ids:
            m = iconkit.META[i]
            (OUT / f"{i}.svg").write_text(build_svg(i, tile=True), encoding="utf-8")
            if not m["png"]:
                continue
            full = build_svg(i, tile=False)
            uri = data_uri(full)
            for size in (180, 192, 512):
                pg = b.new_page(viewport={"width": size, "height": size})
                pg.set_content(f'<body style="margin:0;background:#000"><img src="{uri}" width="{size}" height="{size}" style="display:block"></body>')
                pg.wait_for_function("document.images[0].complete")
                png = pg.screenshot(clip={"x": 0, "y": 0, "width": size, "height": size}, type="png")
                pg.close()
                (OUT / f"{i}-{size}.png").write_bytes(strip_alpha(png))
        if sheet:
            make_sheet(b)
        b.close()
    print("wrote", len(ids), "icons ->", OUT)


def make_sheet(browser) -> None:
    ids = list(iconkit.META)
    apps = [i for i in ids if iconkit.META[i]["png"]]
    tiles = [i for i in ids if not iconkit.META[i]["png"]]

    def img(i, s, label=True, cls="t"):
        uri = data_uri((OUT / f"{i}.svg").read_text(encoding="utf-8"))
        lab = f'<div class="l">{iconkit.META[i]["short"] if cls == "h" else i + "<br>" + iconkit.META[i]["name"]}</div>' if label else ""
        return f'<div class="{cls}"><img src="{uri}" width="{s}" height="{s}">{lab}</div>'

    html = f"""<body style="margin:0;background:#f2f2f4;font:12px/1.4 'Noto Sans CJK JP','Noto Sans JP',sans-serif;color:#222">
<style>
.sec{{padding:22px 28px}} h2{{margin:0 0 14px;font-size:14px}}
.grid{{display:flex;flex-wrap:wrap;gap:18px 22px}}
.t{{width:120px;text-align:center}} .t img{{display:block;border-radius:0;box-shadow:0 2px 8px rgba(0,0,0,.25);border-radius:27px}}
.t .l{{margin-top:6px}}
.wall{{background:linear-gradient(160deg,#2b3a67,#6a3d7c 55%,#c0577f);padding:34px 30px;border-radius:0}}
.hs{{display:grid;grid-template-columns:repeat(6,76px);gap:26px 30px;justify-content:center}}
.h{{width:76px;text-align:center;color:#fff;font-size:11px}}
.h img{{display:block;margin:0 auto;border-radius:13.5px}}
.h .l{{margin-top:5px;text-shadow:0 1px 3px rgba(0,0,0,.5);white-space:nowrap}}
.mini{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}} .mini img{{border-radius:22%;display:block}}
</style>
<div class="sec"><h2>自分たちのアプリ(120px・角丸。PNG も作る)</h2><div class="grid">{''.join(img(i,120) for i in apps)}</div></div>
<div class="sec"><h2>ページ内のタイル専用(120px)</h2><div class="grid">{''.join(img(i,120) for i in tiles)}</div></div>
<div class="wall"><div class="hs">{''.join(img(i,60,cls="h") for i in apps)}</div></div>
<div class="sec"><h2>小さいサイズ(40px / 24px)</h2><div class="mini">{''.join(img(i,40,False) for i in ids)}</div>
<div class="mini" style="margin-top:12px">{''.join(img(i,24,False) for i in ids)}</div></div>
</body>"""
    big = f"""<body style="margin:0;background:#e9e9ee"><div style="display:grid;grid-template-columns:repeat(4,256px);gap:20px;padding:20px">
{''.join(f'<img src="{data_uri((OUT / (i + ".svg")).read_text(encoding="utf-8"))}" width="256" height="256">' for i in ids)}</div></body>"""
    pg = browser.new_page(viewport={"width": 1180, "height": 900}, device_scale_factor=1)
    pg.set_content(big)
    pg.wait_for_function("[...document.images].every(i=>i.complete)")
    pg.screenshot(path=str(WORK / "sheet-large.png"), full_page=True)
    pg.close()
    pg = browser.new_page(viewport={"width": 1180, "height": 900}, device_scale_factor=2)
    pg.set_content(html)
    pg.wait_for_function("[...document.images].every(i=>i.complete)")
    pg.screenshot(path=str(WORK / "sheet.png"), full_page=True)
    pg.close()
    print("sheet ->", WORK / "sheet.png")


def main(argv: list[str]) -> None:
    sheet = "--sheet" in argv
    only = []
    for a in argv:
        if a.startswith("--only="):
            only = a.split("=", 1)[1].split(",")
    if "--only" in argv:
        only = argv[argv.index("--only") + 1].split(",")
    try:
        import playwright  # noqa: F401
    except ImportError:
        if PW_PY and Path(PW_PY).exists() and not os.environ.get("ICONS_REEXEC"):
            env = {**os.environ, "ICONS_REEXEC": "1"}
            sys.exit(subprocess.call([str(PW_PY), "-I", str(Path(__file__).resolve()), *argv], env=env))  # noqa: S603  (持ち主が環境変数で指定した python)
        OUT.mkdir(exist_ok=True)
        for i in iconkit.META:
            (OUT / f"{i}.svg").write_text(build_svg(i, tile=True), encoding="utf-8")
        print("playwright が無いので SVG だけ作りました")
        return
    render_all(only, sheet)


if __name__ == "__main__":
    main(sys.argv[1:])
