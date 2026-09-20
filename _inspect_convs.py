# -*- coding: utf-8 -*-
"""只读：打开指定会话读首条内容，判定是否为自动化遗留（自动化必带那段执行规则指令）。"""
import json
import time

import ui_driver as U

FINGER = "执行规则：如果上面的任务需要我提供材料"
TARGETS = [
    "设计账号内容变现执行规则",
    "执行本月企业财税合规检查演示",
    "编写功能规格书竞品与路线图",
    "设计内容变现方案执行规则",
    "开发贪吃蛇游戏执行规则",
    "生成建筑施工图设计说明执行规则",
]

CLICK_JS = """
((kw) => {
  const side = document.querySelector('aside') || document.body;
  const L = Array.from(side.querySelectorAll('*')).filter(e => e.childElementCount === 0);
  const el = L.reverse().find(e => (((e.innerText || '') + '').trim()).indexOf(kw) === 0);
  if (!el) return { found: false };
  el.scrollIntoView({ block: 'center' });
  el.click();
  return { found: true };
})(%s)
"""

HEAD_JS = """
(() => {
  const v = document.querySelector('.cr-message-list-viewport');
  if (!v) return null;
  return ((v.innerText || '') + '').replace(/\\s+/g, ' ').trim().slice(0, 200);
})()
"""

for t in TARGETS:
    try:
        r1 = U.js(CLICK_JS % json.dumps(t), timeout=30)
    except Exception as e:
        print("--- %s -> 点击失败 %s" % (t, str(e)[:80]))
        continue
    if not (isinstance(r1, dict) and r1.get("found")):
        print("--- %s -> 未找到" % t)
        continue
    time.sleep(2.5)
    try:
        head = U.js(HEAD_JS, timeout=30)
    except Exception as e:
        head = "读取失败 %s" % str(e)[:80]
    auto = FINGER in (head or "") or "执行规则" in (head or "")
    print("--- %s\n    自动化=%s\n    首条: %s" % (t, auto, head))
