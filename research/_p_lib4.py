#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""确保资料库面板打开 → 探查卡片与滚动容器。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402
import cdp as C               # noqa: E402

OPEN_LIB = r"""(async () => {
  const btn = Array.from(document.querySelectorAll('.conversation-list-tab-button'))
    .find(e => (e.innerText||'').replace(/\s+/g,'').replace('更多','') === '资料库');
  if (!btn) return { err: '找不到侧边栏「资料库」' };
  if (!/active/.test(btn.className)) { btn.click(); await sleep(3000); }
  return { ok: true, active: /active/.test(btn.className) };
})()"""

JS = r"""(()=>{
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const rect = e => { const r = e.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  const hits = Array.from(document.querySelectorAll('*')).filter(vis)
    .filter(e => /资料库介绍/i.test(e.innerText || '') && (e.innerText || '').length < 40)
    .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length);
  const scrollers = Array.from(document.querySelectorAll('*')).filter(e => {
    const cs = getComputedStyle(e);
    return /auto|scroll/.test(cs.overflowY) && e.scrollHeight > e.clientHeight + 20;
  }).map(e => ({ tag: e.tagName, cls: String(e.className).slice(0, 70),
                 sh: e.scrollHeight, ch: e.clientHeight, r: rect(e) })).slice(0, 12);
  return { hits: hits.slice(0, 8).map(e => ({ tag: e.tagName, cls: String(e.className).slice(0, 90),
             t: (e.innerText || '').replace(/\s+/g, ' ').slice(0, 60), r: rect(e),
             p: e.parentElement ? String(e.parentElement.className).slice(0, 60) : null })),
           scrollers: scrollers };
})()"""


def main():
    print("open:", json.dumps(U.js(OPEN_LIB, timeout=60), ensure_ascii=False))
    for i in range(8):
        t = C.find_target(url_substr="space/home", type_="iframe")
        if t:
            print("iframe target ready after %ds" % i)
            break
        time.sleep(1.0)
    print(json.dumps(U.eval_in_iframe(JS), ensure_ascii=False, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
