"""dashkit を使う最小の例。合言葉ゲート+アイコン+グラフ1枚(数字はでたらめな例)。

  python3 set_password.py ./example-data        # 合言葉を決める(標準入力)
  uvicorn example.app:app --host 127.0.0.1 --port 8800
  → http://127.0.0.1:8800/
"""
import random
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import gate  # noqa: E402
import iconkit  # noqa: E402

DATA = ROOT / "example-data"
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
gate.install(app, lambda: DATA, cookie="example_gate", title="EXAMPLE", header="example", icon="home")
KIT_FILES = {"kit.css", "kit.js", "fa.js", "fa-emoji.js"}   # 配るのはこの4つだけ(ディレクトリごと配ると gate.json まで見えてしまう)


@app.get("/kit/{name}")
def kit(name: str) -> FileResponse:
    if name not in KIT_FILES:
        raise HTTPException(404)
    return FileResponse(ROOT / name)


@app.get("/api/series")
def series() -> dict[str, list]:
    rnd = random.Random(1)   # noqa: S311  (画面の例に出す作り物の数字。暗号には使わない)
    xs = [f"10/{d}" for d in range(1, 15)]
    return {"xs": xs, "values": [round(40 + rnd.random() * 20, 1) for _ in xs]}


@app.get("/")
def index() -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
{iconkit.head_tags("home")}<title>EXAMPLE</title><link rel="stylesheet" href="/kit/kit.css">
<script src="/kit/fa.js"></script><script src="/kit/fa-emoji.js"></script><script src="/kit/kit.js"></script></head>
<body><main style="padding:24px"><section class="card"><h2>📈 ディスク使用率(例)</h2><div id="g"></div></section></main>
<script>
const api = Kit.api('example');
api('/series').then(d => Kit.line(document.getElementById('g'),
  {{xs: d.xs, series: [{{name: '使用率', color: Kit.C.series[0], values: d.values}}], yFmt: v => v + '%', label: 'ディスク使用率'}}));
</script></body></html>""")
