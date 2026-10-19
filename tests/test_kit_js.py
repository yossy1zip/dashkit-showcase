"""kit.js の純粋な関数(文字の逃がし・金額の書き方・メーター・増減・表)の試験。

node があれば node の vm で kit.js を読み込んで確かめる(DOM は使わない・ネットワークも使わない)。node が無ければ飛ばす。
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")

# kit.js を vm の中で読み、渡した式を順に評価して JSON で返す小さな台
RUNNER = r"""
const vm = require('vm'), fs = require('fs');
const ctx = { addEventListener() {} }; ctx.window = ctx; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx, { filename: 'kit.js' });
const exprs = JSON.parse(fs.readFileSync(0, 'utf8'));
const out = exprs.map(e => vm.runInContext('(K => ' + e + ')(Kit)', ctx));
process.stdout.write(JSON.stringify(out));
"""

EVIL = "<img src=x onerror=alert(1)>\"'&"


def run(*exprs):
    r = subprocess.run([NODE, "-e", RUNNER, str(ROOT / "kit.js")], input=json.dumps(exprs), capture_output=True, text=True, timeout=30, check=True)
    return json.loads(r.stdout)


@unittest.skipIf(NODE is None, "node が無い")
class KitJsTest(unittest.TestCase):
    def test_esc_neutralises_html(self):
        (out,) = run(f"K.esc({json.dumps(EVIL)})")
        self.assertEqual(out, "&lt;img src=x onerror=alert(1)&gt;&quot;&#39;&amp;")
        self.assertEqual(run("K.esc(null)", "K.esc(undefined)", "K.esc(0)"), ["", "", "0"])

    def test_table_and_legend_escape_untrusted_text(self):
        e = json.dumps(EVIL)
        table, leg = run(f"K.tableTwin([{e}, 'v'], [[{e}, {e}]])", f"K.legend([{{name: {e}, color: '#123456'}}])")
        for html in (table, leg):
            self.assertNotIn("<img", html)
            self.assertIn("&lt;img", html)

    def test_short_yen_boundaries(self):
        got = run("K.yenC(0)", "K.yenC(9999)", "K.yenC(10000)", "K.yenC(15000)", "K.yenC(100000)", "K.yenC(1e8)", "K.yenC(1.5e8)", "K.yenC(-15000)")
        self.assertEqual(got, ["0", "9,999", "1万", "1.5万", "10万", "1億", "1.5億", "-1.5万"])

    def test_meter_is_clamped_for_width_and_screen_readers(self):
        for pct, want in ((-5, 0), (0, 0), (42.44, 42), (100, 100), (150, 100), ("NaN", 0)):
            with self.subTest(pct):
                (html,) = run(f"K.meter({pct})")
                self.assertIn(f'aria-valuenow="{want}"', html)
                self.assertIn(f"width:{min(100, max(0, pct if isinstance(pct, (int, float)) else 0)):.1f}%", html)
        (html,) = run(f"K.meter(10, {json.dumps(EVIL)})")
        self.assertNotIn("<img", html)

    def test_delta_uses_symbol_not_only_colour(self):
        up, down_bad, flat, none = run("K.delta(3)", "K.delta(3, {upGood: false})", "K.delta(0)", "K.delta(NaN)")
        self.assertEqual(up, '<span class="up">▲ 3</span>')
        self.assertEqual(down_bad, '<span class="down">▲ 3</span>')   # 支出が増えた=悪い、でも記号は ▲ のまま
        self.assertEqual(flat, '<span class="flat">― 0</span>')
        self.assertEqual(none, "")

    def test_dates_are_zero_padded_local_keys(self):
        self.assertEqual(run("K.dkey(new Date(2026, 0, 5))", "K.pad(7)"), ["2026-01-05", "07"])


if __name__ == "__main__":
    unittest.main()
