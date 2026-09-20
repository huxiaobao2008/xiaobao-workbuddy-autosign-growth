"""诊断：专家团卡片的完整结构 + 点击卡片本体（不点召唤按钮）后会怎样。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_driver as U  # noqa: E402
import ui_tasks as UT  # noqa: E402

CARD_DUMP = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const cards = Array.from(document.querySelectorAll('.ec-expert-card'));
  const c = cards[0];
  if (!c) return { n: 0 };
  return {
    n: cards.length,
    names: cards.map(x => T(x).slice(0, 22)),
    card0_btns: [...c.querySelectorAll('button')].map(b => ({
      t: T(b).slice(0, 18),
      cls: (b.className || '').toString().slice(0, 70),
      tid: b.getAttribute('data-track-id') || null
    })),
    card0_html: c.outerHTML.replace(/\s+/g, ' ').slice(0, 1400)
  };
})()
"""

AFTER_CARD_CLICK = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  return {
    editable: !!document.querySelector('[contenteditable=true]'),
    chips: [...document.querySelectorAll('.cr-chip-label')].map(T),
    detailOpen: !!document.querySelector('.detail-panel'),
    detailText: (() => { const d = document.querySelector('.detail-panel'); return d ? T(d).slice(0, 160) : null; })(),
    overlays: [...document.querySelectorAll('[class*=overlay],[class*=modal]')]
      .filter(e => { const r = e.getBoundingClientRect(); return r.width > 40 && r.height > 40; })
      .map(e => (e.className || '').toString().slice(0, 60)).slice(0, 6),
    url: location.href.slice(-40)
  };
})()
"""

print('=== A. 进专家团 tab ===', flush=True)
U.js('(async()=>{ await openNewTask(); return 1; })()', timeout=60)
time.sleep(1.5)
U.js(UT.EXPERT_ENTER_STEP, timeout=90)
time.sleep(7)
U.js("(async () => { const f = %s; return await f('team', null, 0); })()" % UT._as_fn(UT.EXPERT_PICK_STEP), timeout=90)
time.sleep(7)
# 等卡片出现
r = U.js("""(async () => {
  let c = [];
  for (let i = 0; i < 16; i++) {
    c = Array.from(document.querySelectorAll('.ec-expert-card'));
    if (c.length) break;
    await sleep(600);
  }
  return { n: c.length };
})()""", timeout=120)
print('cards ready:', json.dumps(r, ensure_ascii=False), flush=True)
print(json.dumps(U.js(CARD_DUMP, timeout=60), ensure_ascii=False, indent=1)[:2200], flush=True)

print('\n=== B. 点卡片本体（第一条）===', flush=True)
U.js("""(async () => {
  const c = document.querySelector('.ec-expert-card');
  if (!c) return { err: 'no card' };
  const r = c.getBoundingClientRect();
  const x = r.x + 20, y = r.y + 10;   // 卡片左上角区域，避开召唤按钮
  for (const t of ['pointerdown','mousedown','pointerup','mouseup','click']) {
    c.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t,
      { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y, button: 0, buttons: 1 }));
  }
  return { clicked: true };
})()""", timeout=60)
time.sleep(5)
print(json.dumps(U.js(AFTER_CARD_CLICK, timeout=60), ensure_ascii=False, indent=1)[:1200], flush=True)
