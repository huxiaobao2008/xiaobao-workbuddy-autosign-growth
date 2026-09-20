# -*- coding: utf-8 -*-
"""往「安全中心 → 命令安全 → 放行名单」批量加命令前缀，并回读验证。

用法:
  python cmd_allow.py                # 只读：打印三个名单现状
  python cmd_allow.py add python,node,git
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import ui_driver as U      # noqa: E402
import ui_tasks as UT      # noqa: E402

DUMP = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const m = document.querySelector('.settings-modal');
  const t = m ? T(m) : '';
  // 从「重置为默认」之后开始切，避开概述里「…配置询问和放行名单」那种干扰
  const base = t.indexOf('重置为默认');
  const s = base >= 0 ? t.slice(base) : '';
  const idx = {};
  for (const n of ['程序黑名单', '放行名单', '询问名单']) idx[n] = s.indexOf(n + ' ');
  const order = ['程序黑名单', '放行名单', '询问名单'];
  const out = {};
  for (let k = 0; k < order.length; k++) {
    const n = order[k];
    if (idx[n] < 0) { out[n] = null; continue; }
    let end = s.length;
    for (const o of order) if (idx[o] > idx[n] && idx[o] < end) end = idx[o];
    out[n] = s.slice(idx[n], end).slice(0, 320);
  }
  const inp = document.querySelector('.security-center-panel__plcard-input');
  return JSON.stringify({ onSubPanel: base >= 0, panels: out,
                          editing: !!inp, editingVal: inp ? inp.value : null }, null, 1);
})()
"""

GO = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const m = document.querySelector('.settings-modal');
  if (!m) return { err: '设置没开' };
  const subOpen = () => T(m).indexOf('重置为默认') !== -1;
  if (subOpen()) return { ok: true, already: true };
  for (let attempt = 0; attempt < 3; attempt++) {
    // 用明确的类名定位「命令安全」导航行（别再按"最小的以…开头"猜，会点到描述文字）
    let row = Array.from(m.querySelectorAll('.security-center-panel__nav-row'))
      .find(e => T(e).startsWith('命令安全'));
    if (!row) {
      row = Array.from(m.querySelectorAll('button,div,li'))
        .filter(e => T(e).startsWith('命令安全') && e.querySelectorAll('*').length < 8)
        .sort((a,b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length)[0];
    }
    if (!row) return { err: '找不到命令安全入口' };
    realClick(row);
    for (let i = 0; i < 12; i++) {
      await sleep(400);
      if (subOpen()) return { ok: true, clicked: true, attempt: attempt };
    }
  }
  return { ok: false, err: '点了 3 次命令安全子面板都没展开' };
})()
"""

# 点「放行名单」区块的「添加」（区块名内联，不靠传参）
CLICK_ADD = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const m = document.querySelector('.settings-modal');
  const cands = Array.from(m.querySelectorAll('*')).filter(e => {
    const t = T(e);
    return t.startsWith('放行名单') &&
      Array.from(e.querySelectorAll('button')).some(b => T(b) === '添加');
  }).sort((a,b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length);
  const head = cands[0];
  if (!head) return { err: '找不到放行名单区块' };
  const add = Array.from(head.querySelectorAll('button')).find(b => T(b) === '添加');
  realClick(add);
  await sleep(900);
  const inp = document.querySelector('.security-center-panel__plcard-input');
  return { ok: !!inp, hasInput: !!inp };
})()
"""

# __VAL__ 由 Python 侧替换成 json.dumps(值)；整体是 IIFE，可以直接丢给 U.js
TYPE_AND_ENTER = r"""
(async () => {
  const val = __VAL__;
  const inp = document.querySelector('.security-center-panel__plcard-input');
  if (!inp) return { err: '没有正在编辑的输入框' };
  inp.focus();
  const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  s.call(inp, val);
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  inp.dispatchEvent(new Event('change', { bubbles: true }));
  await sleep(250);
  const typed = inp.value;
  const o = { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true };
  inp.dispatchEvent(new KeyboardEvent('keydown', o));
  inp.dispatchEvent(new KeyboardEvent('keypress', o));
  inp.dispatchEvent(new KeyboardEvent('keyup', o));
  await sleep(900);
  const still = document.querySelector('.security-center-panel__plcard-input');
  return { typed: typed, inputGone: !still, nowVal: still ? still.value : null };
})()
"""


def main():
    do_add = len(sys.argv) > 2 and sys.argv[1] == "add"
    targets = [x.strip() for x in (sys.argv[2].split(",") if len(sys.argv) > 2 else []) if x.strip()]

    r = U.js(UT.OPEN_SETTINGS, timeout=90)
    if not (r or {}).get("ok"):
        U.js(UT.OPEN_SETTINGS, timeout=90)
    time.sleep(2.0)
    UT._js_block(UT.NAV_SETTINGS, "安全中心", timeout=90)
    time.sleep(2.0)
    print("[go] " + json.dumps(U.js(GO, timeout=120), ensure_ascii=False)[:200], flush=True)
    time.sleep(1.0)
    print("[before] " + U.js(DUMP, timeout=60), flush=True)

    if do_add:
        for v in targets:
            # 每加一条都要重新点一次「添加」：回车提交后输入框会关闭
            inp_open = U.js("(()=>!!document.querySelector('.security-center-panel__plcard-input'))()",
                            timeout=30)
            if not inp_open:
                ca = U.js(CLICK_ADD, timeout=120)
                if not (ca or {}).get("ok"):
                    print("[click-add] FAILED %s" % json.dumps(ca, ensure_ascii=False)[:160],
                          flush=True)
            out = U.js(TYPE_AND_ENTER.replace("__VAL__", json.dumps(v)), timeout=60)
            print("[add %s] %s" % (v, json.dumps(out, ensure_ascii=False)[:220]), flush=True)
            time.sleep(0.5)
        print("[after] " + U.js(DUMP, timeout=60), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
