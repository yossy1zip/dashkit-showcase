"""fa_build.load() の試験(合成の SVG を一時ディレクトリに作るだけ・ネットワークは使わない)。実行: python3 -m unittest discover -s tests -v"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fa_build  # noqa: E402


def svg(box="0 0 512 512", paths=('M0 0L10 10Z',), extra=""):
    ps = "".join(f'<path d="{d}"/>' for d in paths)
    vb = f' viewBox="{box}"' if box is not None else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg"{vb}>{extra}{ps}</svg>'


class LoadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fa-build-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "solid").mkdir()
        (self.tmp / "regular").mkdir()

    def put(self, text, name="a", style="solid"):
        (self.tmp / style / f"{name}.svg").write_text(text, encoding="utf-8")

    def assertRejected(self, text, name="a"):
        self.put(text)
        with self.assertRaises(SystemExit):
            fa_build.load(self.tmp, name)

    def test_valid_returns_w_h_d(self):
        self.put(svg(box="0 0 576 512", paths=("M1.5 2.5L-3 4e2Z",)))
        self.assertEqual(fa_build.load(self.tmp, "a"), (576, 512, "M1.5 2.5L-3 4e2Z"))

    def test_r_prefix_reads_regular(self):
        self.put(svg(box="0 0 100 200", paths=("M1 1",)), style="regular")
        self.put(svg(box="0 0 300 400", paths=("M2 2",)), style="solid")
        self.assertEqual(fa_build.load(self.tmp, "r:a"), (100, 200, "M1 1"))
        self.assertEqual(fa_build.load(self.tmp, "a"), (300, 400, "M2 2"))

    def test_whitespace_collapsed(self):
        self.put(svg(paths=("  M0  0\n\n L1 1 \n Z  ",)))
        self.assertEqual(fa_build.load(self.tmp, "a")[2], "M0 0 L1 1 Z")

    def test_viewbox_missing(self):
        self.assertRejected(svg(box=None))

    def test_viewbox_bad_shapes(self):
        for box in ["0 0 -5 512", "0 0 512 -5", "0 0 12345 512", "0 0 512 12345",
                    "0 0 5 512", "0 0 512 512 1", "1 0 512 512", "0 0 512", "0 0 51.2 512", ""]:
            with self.subTest(box=box):
                self.assertRejected(svg(box=box))

    def test_path_count_not_one(self):
        self.assertRejected(svg(paths=()))
        self.assertRejected(svg(paths=("M0 0", "M1 1")))

    def test_path_without_d(self):
        self.assertRejected('<svg viewBox="0 0 512 512"><path fill="red"/></svg>')

    def test_d_bad_characters(self):
        for d in ["M0 0<", "M0 0(1)", "M0 0 url", "M0 0;", "M0 0 alert(1)", "M0 0 &quot;", "M0 0 #", "M0 0 'x'", "M0 0 {}", "M0 0 /", ""]:
            with self.subTest(d=d):
                self.assertRejected(svg(paths=(d,)))

    def test_script_svg_with_bad_d(self):
        self.assertRejected(svg(paths=("M0 0 alert(1)",), extra="<script>alert(1)</script>"))
        self.assertRejected(svg(paths=("M0 0<script>",), extra="<script>alert(1)</script>"))

    def test_quote_cannot_smuggle_into_d(self):
        # d の中の " は属性の終わりになる。どんな入力でも戻ってくる d に " < ( は残らない
        self.put(svg(paths=('M0 0" onload="alert(1)',)))
        try:
            d = fa_build.load(self.tmp, "a")[2]
        except SystemExit:
            return
        self.assertFalse(set('"<(;') & set(d))

    def test_missing_file_does_not_touch_network(self):
        with self.assertRaises(OSError):
            fa_build.load(self.tmp, "nope")


if __name__ == "__main__":
    unittest.main()
