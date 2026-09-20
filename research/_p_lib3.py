#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在资料库 iframe 里找《Workbuddy资料库介绍》卡片 + 滚动容器。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402

JS = r"""(()=>{
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const rect = e => { const r = e.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  // 找含「资料库介绍」的最小可点元素
  const hits = Array.from(document.querySelectorAll('*')).filter(vis)
    .filter(e => /介绍/.test(e.innerText || '') && (e.innerText || '').length < 40)
    .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length);
  // 滚动容器
  const scrollers = Array.from(document.querySelectorAll('*')).filter(e => {
    const cs = getComputedStyle(e);
    return /auto|scroll/.test(cs.overflowY) && e.scrollHeight > e.clientHeight + 20;
  }).map(e => ({ tag: e.tagName, cls: String(e.className).slice(0, 70),
                 sh: e.scrollHeight, ch: e.clientHeight, r: rect(e) })).slice(0, 12);
  return {
    hits: hits.slice(0, 8).map(e => ({ tag: e.tagName, cls: String(e.className).slice(0, 80),
      t: (e.innerText || '').replace(/\s+/g, ' ').slice(0, 60), r: rect(e),
      parentCls: e.parentElement ? String(e.parentElement.className).slice(0, 60) : null })),
    scrollers: scrollers,
    viewport: { w: innerWidth, h: innerHeight }
  };
})()"""

print(json.dumps(U.eval_in_iframe(JS), ensure_ascii=False, indent=1)[:4000])
