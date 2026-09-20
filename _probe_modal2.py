# -*- coding: utf-8 -*-
"""把团队详情弹窗（.ec-modal-card）里的可点元素结构整个 dump 出来，
找真正的「召唤专家团」按钮 —— 现在点 `.ec-modal-summon-btn` 弹窗直接关、没有确认框。

用法: python _probe_modal2.py [idx]
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import ui_driver as U       # noqa: E402
import ui_tasks as UT       # noqa: E402

IDX = int(sys.argv[1]) if len(sys.argv) > 1 else 6

STRUCT = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const card = document.querySelector('.ec-modal-card');
  if (!card) return { err: '弹窗不在' };
  const desc = el => {
    const p = [];
    let n = el;
    while (n && n !== card.parentElement) { p.push(n.tagName + '.' + (n.className||'').toString().slice(0,60)); n = n.parentElement; }
    return p.reverse().join(' > ');
  };
  const nodes = Array.from(card.querySelectorAll('*')).map(el => {
    const r = el.getBoundingClientRect();
    return { tag: el.tagName,
             cls: (el.className||'').toString().slice(0,80),
             txt: T(el).slice(0, 46),
             w: Math.round(r.width), h: Math.round(r.height),
             dis: !!el.disabled,
             cur: getComputedStyle(el).cursor,
             track: el.getAttribute('data-track-id') || '',
             clickable: (getComputedStyle(el).cursor === 'pointer') || el.tagName === 'BUTTON' };
  }).filter(x => x.w > 0 && x.h > 0);
  return { n: nodes.length,
           clickableTexts: nodes.filter(x => x.clickable && x.txt).slice(0, 30),
           allTexts: nodes.filter(x => x.txt).slice(0, 60).map(x => x.tag + ' | ' + x.cls + ' | ' + x.txt) };
})()
"""


def step(name, code, gap=3):
    r = U.js(code, timeout=90)
    print("[%s] %s" % (name, json.dumps(r, ensure_ascii=False)[:300]), flush=True)
    time.sleep(gap)
    return r


pick_fn = UT._as_fn(UT.EXPERT_PICK_STEP)
step("enter", UT.EXPERT_ENTER_STEP, 4)
step("pick-team", "(async () => { const f = %s; return await f('team', null, 0); })()" % pick_fn, 3)
step("open-modal", UT.EXPERT_TEAM_OPEN_MODAL_STEP % IDX, 3)
print("\n---- 弹窗内部结构 ----", flush=True)
d = U.js(STRUCT, timeout=60)
print(json.dumps(d, ensure_ascii=False, indent=1)[:7000], flush=True)
