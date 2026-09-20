# -*- coding: utf-8 -*-
"""列出专家中心的「专家」和「专家团」卡片（序号/名称/简介/使用量），用来挑**简单**的。

用法: python _list_experts.py [expert|team|both]
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import ui_driver as U       # noqa: E402
import ui_tasks as UT       # noqa: E402

WHICH = sys.argv[1] if len(sys.argv) > 1 else "both"

CARDS = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const cards = Array.from(document.querySelectorAll('.ec-expert-card'));
  return { n: cards.length, items: cards.map((c, i) => ({
      i: i,
      txt: T(c).slice(0, 150),
      name: (T(c).match(/^召唤\s*([^\s]{1,20})/) || [])[1] || T(c).slice(0, 20)
  })) };
})()
"""


def step(name, code, gap=3):
    r = U.js(code, timeout=90)
    print("[%s] %s" % (name, json.dumps(r, ensure_ascii=False)[:260]), flush=True)
    time.sleep(gap)
    return r


pick_fn = UT._as_fn(UT.EXPERT_PICK_STEP)
step("enter", UT.EXPERT_ENTER_STEP, 4)

for kind in (["expert", "team"] if WHICH == "both" else [WHICH]):
    print("\n===== %s =====" % kind, flush=True)
    step("pick-" + kind,
         "(async () => { const f = %s; return await f(%s, null, 0); })()" % (pick_fn, json.dumps(kind)), 5)
    d = U.js(CARDS, timeout=60)
    if not isinstance(d, dict) or not d.get("items"):
        print("  读取失败: %s" % json.dumps(d, ensure_ascii=False)[:200], flush=True)
        continue
    print("  共 %d 张" % d["n"], flush=True)
    for it in d["items"]:
        print("  [%2d] %s" % (it["i"], it["txt"]), flush=True)
