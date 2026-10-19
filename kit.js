/* ダッシュボード共通のグラフ部品。依存なし・手書き SVG。
   方針(dataviz スキル): 細い線(2px)・棒は24px以内で先端4px丸め・隙間2px・点は半径4以上で面色のリング・グリッドは細い実線・凡例は常に表示(2系列以上)・
   値は必ずツールチップと「表で見る」で読める・ラベルは textContent で入れる(外から来た文字は信用しない)・文字はデータ色にしない。
   サーバーから来た文字を innerHTML に入れるときは、必ず Kit.esc を通すこと。 */
'use strict';
(function (g) {
  const C = {
    surface: '#1a1a19', ink: '#ffffff', ink2: '#c3c2b7', muted: '#898781', grid: '#2c2c2a', axis: '#383835', empty: '#222221',
    series: ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'],
    heat: ['#16324f', '#1c4d86', '#256abf', '#3987e5', '#5598e7', '#86b6ef', '#cde2fb'],   // 暗い面では「多いほど明るい」(青1色)
  };
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const pad = n => String(n).padStart(2, '0');
  const num = v => Math.round(v).toLocaleString('ja-JP');
  const yen = v => (v < 0 ? '-¥' : '¥') + Math.abs(Math.round(v)).toLocaleString('ja-JP');
  function yenC(v) {   // 軸・タイル用の短い金額
    const a = Math.abs(v), s = v < 0 ? '-' : '';
    if (a >= 1e8) return s + (a / 1e8).toFixed(a >= 1e9 ? 0 : 1).replace('.0', '') + '億';
    if (a >= 1e4) return s + (a / 1e4).toFixed(a >= 1e5 ? 0 : 1).replace('.0', '') + '万';
    return s + Math.round(a).toLocaleString('ja-JP');
  }
  const dkey = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

  function api(header) {
    return async function (path, opt = {}) {
      const r = await fetch('/api' + path, {
        method: opt.method || 'GET', headers: { 'X-Requested-With': header, 'Content-Type': opt.raw ? 'application/octet-stream' : 'application/json', ...(opt.headers || {}) },
        body: opt.raw ? opt.raw : opt.body ? JSON.stringify(opt.body) : undefined,
      });
      if (r.status === 401) { location.reload(); throw new Error('login'); }
      if (!r.ok) { const e = new Error('HTTP ' + r.status); e.status = r.status; try { e.body = await r.json(); } catch (_) { } throw e; }
      return r.json();
    };
  }

  function toast(msg, good) {
    let t = $('#toast');
    if (!t) { t = document.createElement('div'); t.id = 'toast'; document.body.appendChild(t); }
    t.textContent = msg; t.className = 'toast' + (good ? ' good' : ''); t.hidden = false;
    clearTimeout(toast._t); toast._t = setTimeout(() => { t.hidden = true; }, 3600);
  }

  /* ---------------------------------------------------------------- ツールチップ(1つだけ) */
  const tip = {
    el: null,
    show(x, y, head, rows) {
      if (!this.el) { this.el = document.createElement('div'); this.el.className = 'tip'; this.el.hidden = true; document.body.appendChild(this.el); }
      const el = this.el; el.textContent = '';
      if (head) { const h = document.createElement('div'); h.className = 'th'; h.textContent = head; el.appendChild(h); }
      for (const r of rows) {
        const d = document.createElement('div'); d.className = 'tr';
        if (r.c) { const b = document.createElement('b'); b.style.borderColor = r.c; d.appendChild(b); }
        const s = document.createElement('span'); s.textContent = r.l ?? ''; d.appendChild(s);
        const v = document.createElement('strong'); v.textContent = r.v ?? ''; d.appendChild(v);
        el.appendChild(d);
      }
      el.hidden = false;
      const w = el.offsetWidth, h = el.offsetHeight;
      let left = x + 14; if (left + w > innerWidth - 8) left = Math.max(8, x - w - 14);
      let top = y - h - 12; if (top < 8) top = y + 18;
      el.style.left = left + 'px'; el.style.top = top + 'px';
    },
    hide() { if (this.el) this.el.hidden = true; },
  };
  addEventListener('scroll', () => tip.hide(), { passive: true });

  /* ---------------------------------------------------------------- 土台 */
  function mount(el, draw) {
    el.classList.add('chart'); el._draw = draw;
    const run = (force) => { const w = Math.floor(el.clientWidth); if (w < 40) return; if (el._w === w && !force) return; el._w = w; draw(w); };
    if (!el._ro) { el._ro = new ResizeObserver(() => run(false)); el._ro.observe(el); }
    run(true);
  }
  function paint(el, html) {   // 「表で見る」の開閉を保ったまま描き直す
    const open = !!(el.querySelector('details.tv') || {}).open;
    el.innerHTML = html;
    if (open) { const d = el.querySelector('details.tv'); if (d) d.open = true; }
  }
  function tableTwin(head, rows) {
    return `<details class="tv"><summary>表で見る</summary><div class="tbl-wrap"><table class="tbl"><thead><tr>${head.map((h, i) => `<th${i ? ' class="num"' : ''}>${esc(h)}</th>`).join('')}</tr></thead><tbody>${
      rows.map(r => `<tr>${r.map((c, i) => `<td${i ? ' class="num"' : ''}>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`;
  }
  function legend(items, box) {
    return `<div class="legend">${items.map(i => `<span><b class="${box ? 'box' : ''}" style="${box ? 'background' : 'border-color'}:${i.color}"></b>${esc(i.name)}</span>`).join('')}</div>`;
  }
  function niceTicks(lo, hi, n = 4) {
    if (!(hi > lo)) { hi = lo + 1; }
    const step0 = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(step0))), norm = step0 / mag;
    const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
    const a = Math.floor(lo / step) * step, b = Math.ceil(hi / step) * step, t = [];
    for (let v = a; v <= b + step / 2; v += step) t.push(+v.toFixed(10));
    return t;
  }
  function pickLabels(n, max) { const step = Math.max(1, Math.ceil(n / Math.max(1, max))), out = new Set(); for (let i = 0; i < n; i++) if ((n - 1 - i) % step === 0) out.add(i); return out; }   // 右端(最新)を基準に等間隔
  const svgPt = (svg, e) => { const r = svg.getBoundingClientRect(); const vb = svg.viewBox.baseVal; return [(e.clientX - r.left) * vb.width / r.width, (e.clientY - r.top) * vb.height / r.height]; };

  /* ---------------------------------------------------------------- 折れ線
     o: {xs:[ラベル], series:[{name,color,values:[数|null]}], yFmt, xTick(label,i)->文字, height, zero, area, refs:[{y,label}], endLabel, hint} */
  function line(el, o) {
    mount(el, W => {
      const H = o.height || 180, L = o.left || 46, R = 16, T = 12, B = 24, pw = W - L - R, ph = H - T - B, n = o.xs.length;
      const yFmt = o.yFmt || (v => num(v)), ser = o.series;
      let lo = Infinity, hi = -Infinity;
      for (const s of ser) for (const v of s.values) if (v != null) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
      for (const r of o.refs || []) { lo = Math.min(lo, r.y); hi = Math.max(hi, r.y); }
      if (!isFinite(lo)) { lo = 0; hi = 1; }
      if (o.zero !== false && !o.ticks) lo = Math.min(lo, 0);
      const ticks = o.ticks || niceTicks(lo, hi, 4), y0 = ticks[0], y1 = ticks[ticks.length - 1];   // o.ticks で目盛りを固定できる(点数の 1〜5 など)
      const X = i => L + (n === 1 ? pw / 2 : i * pw / (n - 1)), Y = v => T + ph - (v - y0) / (y1 - y0 || 1) * ph;
      let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.label || '折れ線グラフ')}">`;
      for (const t of ticks) s += `<line x1="${L}" x2="${W - R}" y1="${Y(t)}" y2="${Y(t)}" stroke="${t === 0 && lo < 0 ? C.axis : C.grid}" stroke-width="1"/><text x="${L - 6}" y="${Y(t) + 3.5}" text-anchor="end">${esc(yFmt(t))}</text>`;
      const cand = []; o.xs.forEach((x, i) => { const t = o.xTick ? o.xTick(x, i) : x; if (t) cand.push([i, t]); });
      const keep = pickLabels(cand.length, Math.max(2, Math.floor(pw / 62)));
      cand.forEach(([i, t], k) => { if (keep.has(k)) s += `<text x="${X(i)}" y="${H - 6}" text-anchor="${i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle'}">${esc(t)}</text>`; });
      for (const r of o.refs || []) s += `<line x1="${L}" x2="${W - R}" y1="${Y(r.y)}" y2="${Y(r.y)}" stroke="${C.ink2}" stroke-width="1" opacity=".6"/><text x="${W - R}" y="${Y(r.y) - 4}" text-anchor="end" style="fill:${C.ink2}">${esc(r.label)}</text>`;
      for (const sr of ser) {
        let d = '', pen = false, last = -1;
        sr.values.forEach((v, i) => { if (v == null) { pen = false; return; } d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`; pen = true; last = i; });
        if (o.area && ser.length === 1 && d) { const first = sr.values.findIndex(v => v != null); s += `<path d="${d}L${X(last)} ${Y(Math.max(y0, 0))}L${X(first)} ${Y(Math.max(y0, 0))}Z" fill="${sr.color}" opacity=".10" stroke="none"/>`; }
        if (d) s += `<path d="${d}" stroke="${sr.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"${sr.dim ? ' opacity=".55"' : ''}/>`;
        if (last >= 0 && !sr.dim) {
          s += `<circle cx="${X(last)}" cy="${Y(sr.values[last])}" r="4" fill="${sr.color}" stroke="${C.surface}" stroke-width="2"/>`;
          if (o.endLabel) s += `<text x="${Math.min(X(last), W - R - 2)}" y="${Y(sr.values[last]) - 10}" text-anchor="end" style="fill:${C.ink}">${esc(yFmt(sr.values[last]))}</text>`;
        }
      }
      s += `<line id="xh" x1="0" x2="0" y1="${T}" y2="${T + ph}" stroke="${C.ink2}" stroke-width="1" opacity="0"/><g id="dots"></g>`;
      s += `<rect id="hit" x="${L}" y="${T}" width="${pw}" height="${ph}" fill="transparent" tabindex="0"/></svg>`;
      const multi = ser.length > 1;
      paint(el, (multi ? legend(ser.map(x => ({ name: x.name, color: x.color }))) : '') + s +
        (o.hint ? `<div class="note mt2">${esc(o.hint)}</div>` : '') +
        tableTwin(['', ...ser.map(x => x.name)], o.xs.map((x, i) => [x, ...ser.map(sr => sr.values[i] == null ? '—' : yFmt(sr.values[i]))])));
      const svg = el.querySelector('svg'), hit = svg.querySelector('#hit'), xh = svg.querySelector('#xh'), dots = svg.querySelector('#dots');
      const at = e => { const [px] = svgPt(svg, e); return Math.max(0, Math.min(n - 1, Math.round((px - L) / (pw / Math.max(1, n - 1))))); };
      const move = e => {
        const i = n === 1 ? 0 : at(e); xh.setAttribute('x1', X(i)); xh.setAttribute('x2', X(i)); xh.setAttribute('opacity', '.7');
        dots.innerHTML = ser.map(sr => sr.values[i] == null ? '' : `<circle cx="${X(i)}" cy="${Y(sr.values[i])}" r="4" fill="${sr.color}" stroke="${C.surface}" stroke-width="2"/>`).join('');
        tip.show(e.clientX, e.clientY, (o.tipHead ? o.tipHead(o.xs[i], i) : o.xs[i]), ser.filter(sr => sr.values[i] != null).map(sr => ({ c: sr.color, l: sr.name, v: yFmt(sr.values[i]) })));
      };
      const out = () => { xh.setAttribute('opacity', '0'); dots.innerHTML = ''; tip.hide(); };
      hit.addEventListener('pointermove', move); hit.addEventListener('pointerdown', move); hit.addEventListener('pointerleave', out);
    });
  }

  /* ---------------------------------------------------------------- 縦棒(並べる/積む。マイナスも可)
     o: {cats:[ラベル], series:[{name,color,values:[]}], stacked, yFmt, height, xTick, highlight:index} */
  function columns(el, o) {
    mount(el, W => {
      const H = o.height || 190, L = o.left || 46, R = 10, T = 10, B = 24, pw = W - L - R, ph = H - T - B, n = o.cats.length, ser = o.series, yFmt = o.yFmt || num;
      let lo = 0, hi = 0;
      for (let i = 0; i < n; i++) {
        if (o.stacked) { let p = 0, q = 0; for (const s of ser) { const v = s.values[i] || 0; if (v >= 0) p += v; else q += v; } hi = Math.max(hi, p); lo = Math.min(lo, q); }
        else for (const s of ser) { const v = s.values[i] || 0; hi = Math.max(hi, v); lo = Math.min(lo, v); }
      }
      const ticks = niceTicks(lo, hi || 1, 4), y0 = ticks[0], y1 = ticks[ticks.length - 1];
      const Y = v => T + ph - (v - y0) / (y1 - y0 || 1) * ph, base = Y(0), band = pw / n, k = o.stacked ? 1 : ser.length;
      const bw = Math.max(3, Math.min(24, (band - 6) / k - (k > 1 ? 2 : 0)));
      let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.label || '棒グラフ')}">`;
      for (const t of ticks) s += `<line x1="${L}" x2="${W - R}" y1="${Y(t)}" y2="${Y(t)}" stroke="${t === 0 ? C.axis : C.grid}" stroke-width="1"/><text x="${L - 6}" y="${Y(t) + 3.5}" text-anchor="end">${esc(yFmt(t))}</text>`;
      const cand = []; o.cats.forEach((c, i) => { const t = o.xTick ? o.xTick(c, i) : c; if (t) cand.push([i, t]); });
      const keep = pickLabels(cand.length, Math.max(2, Math.floor(pw / 40))), keepIdx = new Map(cand.filter((_, k) => keep.has(k)));
      const bar = (x, a, b, w, color, round) => {   // a=ベースライン側, b=先端。先端だけ4px丸め
        const top = Math.min(a, b), h = Math.abs(b - a); if (h < 0.5) return '';
        const r = Math.min(4, h / 2, w / 2), up = b < a;
        const d = up ? `M${x} ${a}V${top + r}Q${x} ${top} ${x + r} ${top}H${x + w - r}Q${x + w} ${top} ${x + w} ${top + r}V${a}Z`
          : `M${x} ${a}V${top + h - r}Q${x} ${top + h} ${x + r} ${top + h}H${x + w - r}Q${x + w} ${top + h} ${x + w} ${top + h - r}V${a}Z`;
        return round === false ? `<rect x="${x}" y="${top}" width="${w}" height="${h}" fill="${color}"/>` : `<path d="${d}" fill="${color}"/>`;
      };
      for (let i = 0; i < n; i++) {
        const cx = L + band * i + band / 2;
        s += `<g data-g="${i}"${o.highlight != null && o.highlight !== i ? ' opacity=".55"' : ''}>`;
        if (o.stacked) {
          let pos = 0, neg = 0;
          const lastPos = ser.reduce((a, sr, j) => (sr.values[i] || 0) > 0 ? j : a, -1), lastNeg = ser.reduce((a, sr, j) => (sr.values[i] || 0) < 0 ? j : a, -1);
          ser.forEach((sr, j) => {
            const v = sr.values[i] || 0; if (!v) return;
            const from = v > 0 ? pos : neg, to = from + v; if (v > 0) pos = to; else neg = to;
            const isEnd = v > 0 ? j === lastPos : j === lastNeg, dir = v > 0 ? -1 : 1;
            const a = Y(from) + (from !== 0 ? -dir : 0), b = Y(to) + (isEnd ? 0 : -dir);   // 内側の境目は 1px ずつ引いて、2px の隙間にする
            s += bar(cx - bw / 2, a, b, bw, sr.color, isEnd);
          });
        } else ser.forEach((sr, j) => { const v = sr.values[i] || 0; s += bar(cx - (k * (bw + 2) - 2) / 2 + j * (bw + 2), base, Y(v), bw, sr.color); });
        s += '</g>';
        if (keepIdx.has(i)) s += `<text x="${cx}" y="${H - 6}" text-anchor="middle">${esc(keepIdx.get(i))}</text>`;
      }
      s += `<g id="hits">${o.cats.map((_, i) => `<rect data-h="${i}" x="${L + band * i}" y="${T}" width="${band}" height="${ph}" fill="transparent"/>`).join('')}</g></svg>`;
      paint(el, (ser.length > 1 ? legend(ser.map(x => ({ name: x.name, color: x.color })), true) : '') + s +
        tableTwin(['', ...ser.map(x => x.name)], o.cats.map((c, i) => [c, ...ser.map(sr => sr.values[i] == null ? '—' : yFmt(sr.values[i]))])));
      const svg = el.querySelector('svg');
      const gs = $$('g[data-g]', svg);
      const show = (i, e) => {
        gs.forEach((gEl, m) => gEl.setAttribute('opacity', m === i ? '1' : '.5'));
        const rows = ser.map(sr => ({ c: sr.color, l: sr.name, v: yFmt(sr.values[i] || 0) }));
        if (o.stacked && ser.length > 1) rows.push({ c: null, l: '合計', v: yFmt(ser.reduce((a, sr) => a + (sr.values[i] || 0), 0)) });
        tip.show(e.clientX, e.clientY, o.tipHead ? o.tipHead(o.cats[i], i) : o.cats[i], rows);
      };
      const clear = () => { gs.forEach((gEl, m) => gEl.setAttribute('opacity', o.highlight != null && o.highlight !== m ? '.55' : '1')); tip.hide(); };
      $$('rect[data-h]', svg).forEach(r => { const i = +r.dataset.h; r.addEventListener('pointermove', e => show(i, e)); r.addEventListener('pointerdown', e => show(i, e)); r.addEventListener('pointerleave', clear); });
    });
  }

  /* ---------------------------------------------------------------- 横棒(HTML)。1色。marker=比べる値(前月など)
     o: {rows:[{label,value,text,sub,marker}], color, max} */
  function hbars(el, o) {
    const max = o.max || Math.max(1, ...o.rows.map(r => Math.max(r.value, r.marker || 0)));
    el.innerHTML = `<div class="hb">${o.rows.map(r => `<div class="hb-row" data-i="${esc(r.label)}"><span class="nm" title="${esc(r.label)}">${esc(r.label)}</span>
      <span class="bar"><i style="width:${(r.value / max * 100).toFixed(1)}%;background:${o.color || C.series[0]}"></i>${r.marker ? `<u style="left:${(r.marker / max * 100).toFixed(1)}%"></u>` : ''}</span>
      <span class="val">${esc(r.text ?? num(r.value))}</span>${r.sub ? `<span class="sb">${esc(r.sub)}</span>` : ''}</div>`).join('')}</div>`;
  }

  /* ---------------------------------------------------------------- 積み上げ1本(構成比。6区分まで)
     o: {parts:[{label,value,color}], fmt} */
  function stackBar(el, o) {
    const tot = o.parts.reduce((a, p) => a + Math.max(0, p.value), 0) || 1, f = o.fmt || num;
    el.innerHTML = `<div class="stk" style="display:flex;gap:2px;height:18px;border-radius:6px;overflow:hidden">${o.parts.filter(p => p.value > 0).map(p =>
      `<i data-l="${esc(p.label)}" style="flex:${p.value};background:${p.color};min-width:3px"></i>`).join('')}</div>
      ${legend(o.parts.map(p => ({ name: `${p.label} ${f(p.value)}(${Math.round(Math.max(0, p.value) / tot * 100)}%)`, color: p.color })), true)}`;
    $$('.stk i', el).forEach((i, k) => {
      const p = o.parts.filter(x => x.value > 0)[k];
      const show = e => tip.show(e.clientX, e.clientY, p.label, [{ c: p.color, l: '金額', v: f(p.value) }, { c: null, l: '割合', v: Math.round(p.value / tot * 100) + '%' }]);
      i.addEventListener('pointermove', show); i.addEventListener('pointerdown', show); i.addEventListener('pointerleave', () => tip.hide());
    });
  }

  /* ---------------------------------------------------------------- レーダー(5観点など)
     o: {axes:[名前], series:[{name,color,values:[0..max|null],dim}], max, fmt} */
  function radar(el, o) {
    mount(el, W => {
      const S = Math.min(W, 340), cx = W / 2, cy = S / 2 + 4, R = S / 2 - 78, n = o.axes.length, max = o.max || 5, f = o.fmt || (v => v.toFixed(1));
      const ang = i => -Math.PI / 2 + i * 2 * Math.PI / n, P = (i, v) => [cx + Math.cos(ang(i)) * R * v / max, cy + Math.sin(ang(i)) * R * v / max];
      let s = `<svg viewBox="0 0 ${W} ${S + 12}" role="img" aria-label="${esc(o.label || 'レーダーチャート')}">`;
      for (let r = 1; r <= max; r++) s += `<polygon points="${o.axes.map((_, i) => P(i, r).join(',')).join(' ')}" fill="none" stroke="${C.grid}" stroke-width="1"/>`;
      o.axes.forEach((a, i) => {
        const [x, y] = P(i, max), [lx, ly] = P(i, max * 1.17);
        s += `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="${C.grid}" stroke-width="1"/><text x="${lx}" y="${ly + 4}" text-anchor="${Math.abs(lx - cx) < 6 ? 'middle' : lx > cx ? 'start' : 'end'}" style="fill:${C.ink2};font-size:11.5px">${esc(a)}</text>`;
      });
      for (const sr of o.series) {
        const pts = sr.values.map((v, i) => v == null ? null : P(i, v)); if (pts.some(p => !p) || !pts.length) continue;
        s += `<polygon points="${pts.map(p => p.join(',')).join(' ')}" fill="${sr.color}" fill-opacity="${sr.dim ? 0 : .12}" stroke="${sr.color}" stroke-width="${sr.dim ? 1.5 : 2}" stroke-linejoin="round"${sr.dim ? ' opacity=".6"' : ''}/>`;
        if (!sr.dim) pts.forEach(p => { s += `<circle cx="${p[0]}" cy="${p[1]}" r="4" fill="${sr.color}" stroke="${C.surface}" stroke-width="2"/>`; });
      }
      o.axes.forEach((_, i) => { const [x, y] = P(i, max * .75); s += `<circle data-a="${i}" cx="${x}" cy="${y}" r="26" fill="transparent"/>`; });
      s += '</svg>';
      paint(el, (o.series.length > 1 ? legend(o.series.map(x => ({ name: x.name, color: x.color }))) : '') + s +
        tableTwin(['観点', ...o.series.map(x => x.name)], o.axes.map((a, i) => [a, ...o.series.map(sr => sr.values[i] == null ? '—' : f(sr.values[i]))])));
      $$('circle[data-a]', el).forEach(c => { const i = +c.dataset.a; const show = e => tip.show(e.clientX, e.clientY, o.axes[i], o.series.filter(sr => sr.values[i] != null).map(sr => ({ c: sr.color, l: sr.name, v: f(sr.values[i]) }))); c.addEventListener('pointermove', show); c.addEventListener('pointerdown', show); c.addEventListener('pointerleave', () => tip.hide()); });
    });
  }

  /* ---------------------------------------------------------------- カレンダー・ヒート(日ごとの値)
     o: {from:'YYYY-MM-DD', to, values:{日付:数}, min, max, fmt(v)->文字, lo:'低', hi:'高', unit} */
  function heatCal(el, o) {
    mount(el, W => {
      const parse = k => { const [y, m, d] = k.split('-').map(Number); return new Date(y, m - 1, d); };
      const from = parse(o.from), to = parse(o.to), start = new Date(from); start.setDate(start.getDate() - ((start.getDay() + 6) % 7));   // 月曜始まり
      const weeks = Math.ceil(((to - start) / 864e5 + 1) / 7), L = 22, T = 16, gap = 2, cell = Math.max(8, Math.min(18, Math.floor((W - L - 4) / weeks) - gap));
      const f = o.fmt || (v => String(v)), lo = o.min ?? 1, hi = o.max ?? 5;
      const vw = L + weeks * (cell + gap);   // マスは 18px で頭打ち。広い枠でも引き伸ばさない(文字まで大きくなるため)
      let s = `<svg viewBox="0 0 ${vw} ${T + 7 * (cell + gap)}" style="max-width:${vw}px" role="img" aria-label="${esc(o.label || 'カレンダー')}">`;
      ['月', '', '水', '', '金', '', '日'].forEach((d, r) => { if (d) s += `<text x="0" y="${T + r * (cell + gap) + cell - 2}">${d}</text>`; });
      const rows = []; let lastM = -1;
      for (let w = 0; w < weeks; w++) for (let r = 0; r < 7; r++) {
        const d = new Date(start); d.setDate(start.getDate() + w * 7 + r);
        if (d < from || d > to) continue;
        const k = dkey(d), v = o.values[k], x = L + w * (cell + gap), y = T + r * (cell + gap);
        if (r === 0 || (w === 0 && r === 0)) { if (d.getMonth() !== lastM) { lastM = d.getMonth(); s += `<text x="${x}" y="10">${d.getMonth() + 1}月</text>`; } }
        const col = v == null ? C.empty : C.heat[Math.max(0, Math.min(C.heat.length - 1, Math.round((v - lo) / (hi - lo || 1) * (C.heat.length - 1))))];
        s += `<rect data-d="${k}" x="${x}" y="${y}" width="${cell}" height="${cell}" rx="3" fill="${col}"/>`;
        if (v != null) rows.push([k, f(v)]);
      }
      s += '</svg>';
      const sw = C.heat.map(c => `<i style="display:inline-block;width:14px;height:10px;background:${c};border-radius:2px;margin-right:2px"></i>`).join('');
      paint(el, s + `<div class="legend mt2"><span>${esc(o.lo || '低')} ${sw} ${esc(o.hi || '高')}</span><span><i style="display:inline-block;width:14px;height:10px;background:${C.empty};border-radius:2px"></i> 記録なし</span></div>` + tableTwin(['日付', o.unit || '値'], rows));
      $$('rect[data-d]', el).forEach(r => { const k = r.dataset.d, v = o.values[k]; const show = e => tip.show(e.clientX, e.clientY, k, [{ c: v == null ? null : C.series[0], l: o.unit || '値', v: v == null ? '記録なし' : f(v) }]); r.addEventListener('pointermove', show); r.addEventListener('pointerdown', show); r.addEventListener('pointerleave', () => tip.hide()); });
    });
  }

  /* ---------------------------------------------------------------- 小さな部品 */
  function spark(values, o = {}) {
    const w = o.w || 100, h = o.h || 26, c = o.color || C.series[0], v = values.filter(x => x != null);
    if (v.length < 2) return '';
    const lo = Math.min(...v), hi = Math.max(...v), X = i => 5 + i * (w - 10) / (values.length - 1), Y = x => h - 5 - (x - lo) / ((hi - lo) || 1) * (h - 10);
    let d = '', pen = false, last = -1; values.forEach((x, i) => { if (x == null) { pen = false; return; } d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(x).toFixed(1)}`; pen = true; last = i; });
    return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none" aria-hidden="true"><path d="${d}" stroke="${C.muted}" stroke-width="2" vector-effect="non-scaling-stroke" opacity=".8"/><circle cx="${X(last)}" cy="${Y(values[last])}" r="4" fill="${c}" stroke="${C.surface}" stroke-width="2"/></svg>`;
  }
  function meter(pct, label) {   // 0〜100 に丸める(幅も読み上げの値も。NaN は 0)
    const p = Math.max(0, Math.min(100, +pct || 0));
    return `<div class="meter" role="progressbar" aria-valuenow="${Math.round(p)}" aria-valuemin="0" aria-valuemax="100" aria-label="${esc(label || '進み具合')}"><i style="width:${p.toFixed(1)}%"></i></div>`;
  }
  function delta(v, o = {}) {   // 色だけにせず ▲▼ と言葉を付ける。upGood=false なら増えるのが悪い(支出など)
    if (v == null || !isFinite(v)) return '';
    const upGood = o.upGood !== false, f = o.fmt || (x => num(Math.abs(x))), s = Math.abs(v) < 1e-9 ? 'flat' : (v > 0) === upGood ? 'up' : 'down';
    return `<span class="${s}">${v > 0 ? '▲' : v < 0 ? '▼' : '―'} ${esc(f(v))}${o.suffix ? esc(o.suffix) : ''}</span>`;
  }

  /* ---------------------------------------------------------------- タブ(#hash) */
  function tabs(names, onShow) {
    const go = () => {
      let t = location.hash.replace('#', '').split('/')[0]; if (!names.includes(t)) t = names[0];
      names.forEach(n => { const s = $('#tab-' + n); if (s) s.hidden = n !== t; });
      $$('.kit-tabs a').forEach(a => a.classList.toggle('on', a.dataset.go === t));
      scrollTo(0, 0); tip.hide(); onShow(t);
    };
    addEventListener('hashchange', go); go();
    return go;
  }

  g.Kit = { C, esc, $, $$, pad, num, yen, yenC, dkey, api, toast, tip, line, columns, hbars, stackBar, radar, heatCal, spark, meter, delta, tabs, tableTwin, legend };
})(window);
