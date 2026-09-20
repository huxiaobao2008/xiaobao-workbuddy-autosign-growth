"""诊断：专家团卡片的结构与召唤后输入框里的 chip 到底是什么。
"""
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
  return {
    n: cards.length,
    card0: c ? { text: T(c).slice(0, 120),
                 btns: [...c.querySelectorAll('button')].map(b => ({ t: T(b).slice(0, 20),
                        cls: (b.className || '').toString().slice(0, 60) })),
                 cls: (c.className || '').toString(),
                 htmlLen: c.innerHTML.length } : null,
    gridItemCls: c && c.parentElement ? (c.parentElement.className || '').toString() : null
  };
})()
"""

CHIP_DUMP = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const chips = [...document.querySelectorAll('.cr-status-chips *')]
    .filter(e => e.children.length === 0).map(e => ({ c: (e.className || '').toString().slice(0, 50), t: T(e) }));
  const box = document.querySelector('.cr-input-box__main');
  return { chips: chips.slice(0, 12),
           statusChipsHTML: (document.querySelector('.cr-status-chips') || {}).outerHTML ?
             document.querySelector('.cr-status-chips').outerHTML.replace(/\s+/g, ' ').slice(0, 700) : null,
           edText: (() => { const e = document.querySelector('[contenteditable=true]'); return e ? T(e).slice(0, 60) : null; })() };
})()
"""

print('=== 1. 进专家团 tab，dump 卡片结构 ===', flush=True)
U.js('(async()=>{ await openNewTask(); return 1; })()', timeout=60)
time.sleep(1.5)
U.js(UT.EXPERT_ENTER_STEP, timeout=90)
time.sleep(6)
U.js("(async () => { const f = %s; return await f('team', null, 0); })()" % UT._as_fn(UT.EXPERT_PICK_STEP), timeout=90)
time.sleep(6)
print(json.dumps(U.js(CARD_DUMP, timeout=60), ensure_ascii=False, indent=1)[:1800], flush=True)

print('\n=== 2. 召唤后 chip 细节 ===', flush=True)
print(json.dumps(U.js("(async () => { const f = %s; return await f('team', 0); })()" % UT._as_fn(UT.EXPERT_SUMMON_STEP), timeout=120),
                 ensure_ascii=False)[:300], flush=True)
time.sleep(5)
print(json.dumps(U.js(CHIP_DUMP, timeout=60), ensure_ascii=False, indent=1)[:1800], flush=True)
