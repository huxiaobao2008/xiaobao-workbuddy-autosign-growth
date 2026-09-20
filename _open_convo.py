# -*- coding: utf-8 -*-
"""打开侧边栏里某条会话（按标题关键词）并 dump 正文 + 截图。

用法: python _open_convo.py DID
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import ui_driver as U       # noqa: E402

KW = sys.argv[1] if len(sys.argv) > 1 else ""

OPEN = r"""
(async () => {
  const T = e => (e.innerText || '').replace(/\s+/g, ' ').trim();
  const items = Array.from(document.querySelectorAll('.conversation-item'));
  const it = items.find(e => T(e).indexOf(%s) !== -1);
  if (!it) return { err: 'not found', have: items.map(e => T(e).slice(0, 40)) };
  const card = it.querySelector('.cb-agent-card') || it;
  realClick(card);
  await sleep(2500);
  return { ok: true, t: T(it).slice(0, 80) };
})()
""" % json.dumps(KW)

VIEW = r"""
(() => {
  const v = document.querySelector('.cr-message-list-viewport');
  if (!v) return 'no view';
  return (v.innerText || '').replace(/\n{2,}/g, '\n').slice(-2500);
})()
"""

print("open:", json.dumps(U.js(OPEN, timeout=90), ensure_ascii=False), flush=True)
time.sleep(3)
print("\n---- 正文 ----", flush=True)
print(U.js(VIEW, timeout=60), flush=True)
print("\nshot:", json.dumps(U.shot("_shot_convo.png"), ensure_ascii=False), flush=True)
