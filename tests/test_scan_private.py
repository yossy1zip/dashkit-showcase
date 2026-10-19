"""scripts/scan_private.py の試験(合成の文字列だけ。ここに書いた値はすべて作り物)。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import scan_private  # noqa: E402


def kinds(text):
    return [k for _, k, _ in scan_private.scan_text(text)]


class ScanTest(unittest.TestCase):
    def test_finds_each_kind(self):
        cases = {
            "-----BEGIN OPENSSH PRIVATE KEY-----": "秘密鍵",
            "token = ghp_" + "a1B2" * 9: "トークンの形",
            "AKIA" + "ABCDEFGHIJKLMNOP": "トークンの形",
            "host 192.168.10.20": "IPv4",
            "dns 10.0.0.1:53": "IPv4",
            "mail someone@my-own-domain.jp": "メール",
            "data at /mnt/pool/photos": "内部のパス",
            "cd /opt/myapp && run": "内部のパス",
            "ssh nas.local": "内部の名前",
            "printer.home.arpa": "内部の名前",
        }
        for text, kind in cases.items():
            with self.subTest(text):
                self.assertIn(kind, kinds(text))

    def test_allows_placeholders(self):
        ok = [
            "uvicorn app:app --host 127.0.0.1 --port 8800",
            "bind 0.0.0.0",
            "mail admin@example.com / 123+abc@users.noreply.github.com",
            "data dir /srv/example/db",
            "python3 -m unittest  # fastapi 0.148.0",
            "Font Awesome 6.6.0",                 # 3つ組の版番号は IP ではない(4つ組は見分けられないので拾う)
            "path ./opt/x and https://example.com/home/page",   # 相対パス・URL の中は内部のパスとみなさない
            "the .local suffix",                  # 名前ではない
        ]
        for text in ok:
            with self.subTest(text):
                self.assertEqual(kinds(text), [])

    def test_ip_with_octet_over_255_is_not_ip(self):
        self.assertEqual(kinds("version 1.2.300.4"), [])

    def test_reports_line_numbers(self):
        self.assertEqual(scan_private.scan_text("a\nb 172.16.0.9\n")[0][:2], (2, "IPv4"))


if __name__ == "__main__":
    unittest.main()
