# -*- coding: utf-8 -*-
"""抓「召唤专家团」弹窗现场的 DOM：看到底有没有「使用提醒」确认框、按钮叫什么。

用法: python _probe_modal.py [idx]
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import ui_driver as U       # noqa: E402
import ui_tasks as UT       # noqa: E402

IDX = int(sys.argv[1]) if len(sys.argv) > 1 else 6

DUMP = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = el => { const r = el.getBoundingClientRect();
                      return r.width > 0 && r.height > 0; };
  const out = { url: location.href, hidden: document.hidden };
  const cands = Array.from(document.querySelectorAll('div,section'))
    .filter(el => /overlay|dialog|modal|popup|mask|confirm/i.test((el.className||'').toString()))
    .filter(vis);
  out.dialogs = cands.slice(0, 14).map(el => ({
    cls: (el.className || '').toString().slice(0, 130),
    txt: T(el).slice(0, 260),
    w: Math.round(el.getBoundingClientRect().width),
    h: Math.round(el.getBoundingClientRect().height)
  }));
  out.ackKnown = Array.from(document.querySelectorAll('*'))
    .filter(el => (el.innerText || '').indexOf('已知悉') !== -1)
    .slice(0, 4)
    .map(el => ({ cls: (el.className||'').toString().slice(0,90), txt: T(el).slice(0,150) }));
  out.buttons = Array.from(document.querySelectorAll('button,[role=button]'))
    .filter(vis)
    .map(b => ({ t: T(b).slice(0, 26), dis: !!b.disabled }))
    .filter(x => x.t);
  out.modalBtn = (() => {
    const b = document.querySelector('.ec-modal-summon-btn');
    return b ? { txt: T(b), dis: !!b.disabled, vis: vis(b) } : null;
  })();
  return out;
})()
"""


def step(name, code, gap=3):
    r = U.js(code, timeout=90)
    print("[%s] %s" % (name, json.dumps(r, ensure_ascii=False)[:400]), flush=True)
    time.sleep(gap)
    return r


pick_fn = UT._as_fn(UT.EXPERT_PICK_STEP)
print("== 进入专家中心 ==", flush=True)
step("enter", UT.EXPERT_ENTER_STEP, 4)
step("pick-team", "(async () => { const f = %s; return await f('team', null, 0); })()" % pick_fn, 3)
print("== 打开第 %d 张卡片 ==" % IDX, flush=True)
step("open-modal", UT.EXPERT_TEAM_OPEN_MODAL_STEP % IDX, 3)
print("\n---- 弹窗现场（点击前）----", flush=True)
print(json.dumps(U.js(DUMP, timeout=60), ensure_ascii=False, indent=1)[:4000], flush=True)
print("\n== 点「召唤专家团」==", flush=True)
step("modal-summon", UT.EXPERT_TEAM_MODAL_SUMMON_STEP, 4)
print("\n---- 弹窗现场（点击后）----", flush=True)
print(json.dumps(U.js(DUMP, timeout=60), ensure_ascii=False, indent=1)[:5000], flush=True)
