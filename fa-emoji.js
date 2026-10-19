/* 絵文字を Font Awesome Free のアイコンに置き換える(iOS のカラー絵文字が画面の雰囲気に合わないため)。
   fa.js のあとに読み込む。画面に出た文字の中の絵文字を、同じ意味の <svg> に差し替える。あとから描かれた部分(JS が足した文字)も、MutationObserver で追いかける。
   - 対応表(MAP)にある絵文字は、そのアイコンに。表に無い絵文字は消す(カラーの絵文字を残さないため)。新しい絵文字を使うときは MAP に足す(名前は fa_build.py が自動で fa.js に取り込む)。
   - ▶ ◀ ↩ ⚠ ⬇ ⏱ など、iOS が絵文字として描きがちな記号も表にある。→ ↗ ✓ ✕ ▲ ▼ などの文字の記号は、そのまま。
   - 触らないところ: textarea・input・select・script・style・contenteditable、`data-keep-emoji` を付けた要素、`window.FA_EMOJI_SKIP`(CSS セレクタ)に当たる要素(本人が書いた文は、書いたまま見せるため)。option と title は、消すだけ。
   - アイコンは Font Awesome Free(CC BY 4.0。fa.js に表示)。 */
(function (g) {
  'use strict';
  if (g.__faEmoji || typeof g.fa !== 'function') return;
  g.__faEmoji = true;
  const G = '#3fb950', A = '#e3a008', R = '#e5534b', B = '#4f8ff7', P = '#ec6aa6';
  /*MAP-BEGIN*/
  const MAP = {
    // 画面・道具
    '🏠': ['house'], '📂': ['folder-open'], '📁': ['folder-open'], '📄': ['file'], '📃': ['file'], '📋': ['clipboard'], '📝': ['pen-to-square'], '✏': ['pencil'], '🖊': ['pen'],
    '📌': ['thumbtack'], '📍': ['location-dot'], '🔖': ['bookmark'], '🗒': ['note-sticky'], '📓': ['book'], '📔': ['book'], '📕': ['book'], '📖': ['book-open'], '📚': ['book-open'],
    '📅': ['calendar-days'], '📆': ['calendar-days'], '🗓': ['calendar-days'], '🕐': ['clock'], '⏰': ['clock'], '⏱': ['stopwatch'], '⏳': ['hourglass-half'], '⌛': ['hourglass-half'],
    '🔍': ['magnifying-glass'], '🔎': ['magnifying-glass'], '🔗': ['link'], '🌐': ['globe'], '⚙': ['gear'], '🛠': ['screwdriver-wrench'], '🔧': ['wrench'], '🔨': ['hammer'],
    '🔒': ['lock'], '🔓': ['lock-open'], '🔑': ['key'], '🛡': ['shield-halved'], '🔔': ['bell'], '📣': ['bullhorn'], '📢': ['bullhorn'],
    '💾': ['floppy-disk'], '🖥': ['desktop'], '💻': ['laptop'], '📱': ['mobile-screen'], '🗑': ['trash'], '📥': ['inbox'], '📤': ['file-export'], '✉': ['envelope'], '📧': ['envelope'],
    '📎': ['paperclip'], '🧰': ['toolbox'], '🔌': ['plug'], '🖨': ['print'], '📦': ['box'], '🗂': ['folder-open'],
    // 数字・状態
    '📊': ['chart-column'], '📈': ['chart-line'], '📉': ['chart-line'], '🎯': ['bullseye'], '💡': ['lightbulb'], '🔥': ['fire'], '⚡': ['bolt'], '⭐': ['star'], '🌟': ['star'],
    '✨': ['wand-magic-sparkles'], '🧠': ['brain'], '🚀': ['rocket'], '🏆': ['trophy'], '🎉': ['gift'], '🎁': ['gift'], '🏁': ['flag'], '🚩': ['flag'], '🧭': ['compass'],
    '✅': ['circle-check', G], '☑': ['square-check'], '✔': ['check'], '❌': ['circle-xmark', R], '✖': ['xmark'], '❎': ['xmark'], '⚠': ['triangle-exclamation', A], '❗': ['circle-exclamation', R],
    '❓': ['circle-question'], 'ℹ': ['circle-info'], '🆕': ['circle-plus'], '➕': ['plus'], '➖': ['minus'], '🔄': ['rotate'], '🔁': ['repeat'], '🔂': ['repeat'], '🔀': ['shuffle'],
    '🟢': ['circle', G], '🟡': ['circle', A], '🔴': ['circle', R], '🟠': ['circle', '#f08a3c'], '🔵': ['circle', B], '🟣': ['circle', '#9b8afb'], '⚪': ['circle', '#bbb'], '⚫': ['circle', '#555'],
    '🟦': ['square', B], '🟩': ['square', G], '🟨': ['square', A], '🟥': ['square', R], '⬛': ['square', '#555'], '⬜': ['square', '#bbb'],
    // 矢印・操作
    '⬇': ['arrow-down'], '⬆': ['arrow-up'], '➡': ['arrow-right'], '⬅': ['arrow-left'], '↩': ['reply'], '↪': ['share'], '↔': ['arrows-left-right'], '▶': ['play'], '◀': ['play', null, 'flip'],
    '⏸': ['pause'], '⏯': ['play'], '⏭': ['forward-step'], '⏮': ['backward-step'], '⏩': ['forward'], '⏪': ['backward'], '⛶': ['expand'], '🔲': ['maximize'], '▦': ['table-cells-large'],
    // メディア・声
    '🔊': ['volume-high'], '🔈': ['volume-low'], '🔇': ['volume-xmark'], '🎵': ['music'], '🎶': ['music'], '🎧': ['headphones'], '🎤': ['microphone'], '📷': ['camera'], '📸': ['camera'],
    '🎞': ['film'], '🎬': ['clapperboard'], '📹': ['video'], '🖼': ['image'], '🎨': ['palette'], '🎮': ['gamepad'], '🙈': ['eye-slash'], '👀': ['eye'], '👁': ['eye'],
    // 人・気持ち・生き物
    '💬': ['comment'], '🗨': ['comment'], '💭': ['comment-dots'], '🤖': ['robot'], '👤': ['user'], '👥': ['user-group'], '🧑': ['user'], '👍': ['thumbs-up'], '👎': ['thumbs-down'],
    '♥': ['heart'], '♡': ['r:heart'], '❤': ['heart', R], '💗': ['heart', P], '💖': ['heart', P], '💕': ['heart', P], '💜': ['heart', '#9b8afb'], '💙': ['heart', B], '💚': ['heart', G],
    '😀': ['face-smile'], '😊': ['face-smile'], '🙂': ['face-smile'], '😅': ['face-smile'], '😢': ['face-frown'], '😭': ['face-frown'], '😡': ['face-angry'], '🥺': ['face-frown'],
    '🥚': ['egg'], '🐣': ['kiwi-bird'], '🐥': ['dove'], '🦉': ['crow'], '🐉': ['dragon'], '🐱': ['cat'], '🐶': ['dog'], '🌱': ['seedling'], '🌿': ['leaf'], '🍃': ['leaf'], '🌳': ['tree'],
    '🌙': ['moon'], '🌛': ['moon'], '🌓': ['circle-half-stroke'], '☀': ['sun'], '🌤': ['sun'], '☁': ['cloud'], '🌧': ['cloud-rain'], '❄': ['snowflake'], '🌈': ['rainbow'],
    // 暮らし・お金・仕事
    '💰': ['sack-dollar'], '💴': ['sack-dollar'], '💵': ['sack-dollar'], '💳': ['credit-card'], '🏦': ['building-columns'], '💼': ['briefcase'], '🏢': ['building'], '🎓': ['graduation-cap'],
    '🚗': ['car'], '🚃': ['train'], '✈': ['plane'], '☕': ['mug-hot'], '🍺': ['beer-mug-empty'], '🚬': ['smoking'], '🏃': ['person-running'], '🛏': ['bed'], '🩺': ['stethoscope'], '💊': ['pills'],
    '🛒': ['cart-shopping'], '🎂': ['cake-candles'], '🍽': ['utensils'], '🔋': ['battery-full'], '🕹': ['gamepad'],
    // 画面の走査で見つかった追加分
    '🧩': ['puzzle-piece'], '🤝': ['handshake'], '📰': ['newspaper'], '🏷': ['tag'], '⛏': ['cube'], '✍': ['pen-nib'], '🪄': ['wand-magic'], '🧹': ['broom'],
    '⌚': ['clock'], '🤍': ['heart', '#e8e8e8'], '🎀': ['ribbon'], '🫧': ['droplet']
  };
  /*MAP-END*/
  const SKIP = 'textarea,input,select,option,script,style,noscript,svg,title,[contenteditable],[data-keep-emoji],.fae';
  const STRIP_ONLY = 'option,title';
  const VS = /️|︎/g;
  const keys = Object.keys(MAP).map(k => k.trim().replace(VS, '')).filter((k, i, a) => k && a.indexOf(k) === i).sort((a, b) => b.length - a.length);
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  // 表にある絵文字 + 絵文字全般(1F300〜1FAFF、2600〜27BF のうち、文字の記号 ✓ ✕ ✧ は除く)。後ろの異体字セレクタ・ZWJ つなぎも一緒に
  const RE_SRC = '(?:' + keys.map(esc).join('|') + '|[\\u{1F300}-\\u{1FAFF}\\u{2600}-\\u{2712}\\u{2714}\\u{2716}-\\u{2726}\\u{2728}-\\u{27BF}])\\uFE0F?(?:\\u200D[\\u{1F000}-\\u{1FAFF}\\u2640\\u2642\\u2695-\\u2696]\\uFE0F?)*(?:[\\u{1F3FB}-\\u{1F3FF}])?';
  const RE_G = new RegExp(RE_SRC, 'gu'), RE_T = new RegExp(RE_SRC, 'u');
  const unknown = new Set();

  function iconFor(m) {
    const k = m.replace(VS, '');
    let e = MAP[k];
    if (!e) { const first = Array.from(k)[0]; e = MAP[first]; }
    return e;
  }
  function make(e) {
    const s = document.createElement('span');
    s.className = 'fae' + (e[2] ? ' ' + e[2] : '');
    s.setAttribute('role', 'img');
    s.innerHTML = g.fa(e[0]);
    if (e[1]) s.style.color = e[1];
    return s;
  }
  function convertText(node) {
    const t = node.nodeValue, p = node.parentNode;
    if (!p || !RE_T.test(t)) return;
    if (p.closest && p.closest(SKIP)) { if (p.closest(STRIP_ONLY)) node.nodeValue = t.replace(RE_G, ''); return; }
    const sk = g.FA_EMOJI_SKIP; if (sk && p.closest && p.closest(sk)) return;
    const frag = document.createDocumentFragment();
    let last = 0, m;
    RE_G.lastIndex = 0;
    while ((m = RE_G.exec(t))) {
      if (m.index > last) frag.appendChild(document.createTextNode(t.slice(last, m.index)));
      const e = iconFor(m[0]);
      if (e) frag.appendChild(make(e)); else unknown.add(m[0]);   // 表に無い絵文字は、出さない
      last = m.index + m[0].length;
    }
    if (last < t.length) frag.appendChild(document.createTextNode(t.slice(last)));
    p.replaceChild(frag, node);
  }
  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) { convertText(root); return; }
    if (root.nodeType !== 1 || (root.closest && root.closest('.fae'))) return;
    const out = [], tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    for (let n = tw.nextNode(); n; n = tw.nextNode()) if (RE_T.test(n.nodeValue)) out.push(n);
    out.forEach(convertText);
  }
  g.faEmojiConvert = walk;
  g.faEmojiUnknown = () => Array.from(unknown);

  const css = document.createElement('style');
  css.textContent = '.fae{display:inline-flex;align-items:center;justify-content:center;vertical-align:-.14em;line-height:1;pointer-events:none}.fae svg.fa{width:1em;height:1em;fill:currentColor;stroke:none}.fae.flip svg{transform:scaleX(-1)}';
  document.head.appendChild(css);

  const start = () => {
    walk(document.body);
    new MutationObserver(ms => {
      for (const m of ms) {
        if (m.type === 'characterData') walk(m.target);
        else m.addedNodes.forEach(n => walk(n));
      }
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  };
  if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
})(window);
