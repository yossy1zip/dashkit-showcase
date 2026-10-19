"""set_password.py の試験(子プロセスで動かす・データ領域は一時ディレクトリ・chown は試験しない)。"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "set_password.py"
sys.path.insert(0, str(ROOT))
import gate  # noqa: E402

PW = "tesuto-awase-kotoba-1"


def run(args, stdin):
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin, capture_output=True, text=True, timeout=60, cwd=ROOT)


class SetPasswordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="setpw-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.data = self.tmp / "data"

    def test_writes_gate_json_600_without_echoing_password(self):
        r = run([str(self.data)], PW + "\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(PW, r.stdout)
        self.assertNotIn(PW, r.stderr)
        p = self.data / "gate.json"
        self.assertTrue(p.is_file())
        self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)
        obj = json.loads(p.read_text())
        self.assertEqual({"v", "salt", "hash", "secret"}, set(obj))
        self.assertNotIn(PW, p.read_text())
        # 末尾の改行は合言葉に含めない
        self.assertEqual(obj["hash"], gate._hash(PW, bytes.fromhex(obj["salt"])))
        self.assertFalse(list(self.data.glob("*.tmp")))

    def test_too_short_is_refused(self):
        r = run([str(self.data)], "abc\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("4", r.stderr)
        self.assertFalse((self.data / "gate.json").exists())

    def test_four_chars_is_accepted(self):
        r = run([str(self.data)], "abcd")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.data / "gate.json").exists())

    def test_empty_stdin_is_refused(self):
        r = run([str(self.data)], "")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.data / "gate.json").exists())

    def test_no_args_prints_usage(self):
        r = run([], PW + "\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("set_password.py", r.stdout + r.stderr)
        self.assertNotIn(PW, r.stdout + r.stderr)
        self.assertFalse(self.data.exists())

    def test_rerun_replaces_hash_and_keeps_600(self):
        run([str(self.data)], "first-pass\n")
        a = json.loads((self.data / "gate.json").read_text())
        r = run([str(self.data)], "second-pass\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        b = json.loads((self.data / "gate.json").read_text())
        self.assertNotEqual(a["hash"], b["hash"])
        self.assertNotEqual(a["secret"], b["secret"])
        self.assertEqual(stat.S_IMODE(os.stat(self.data / "gate.json").st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
