#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在已打开的资料库文档页里找正文滚动容器与正文元素。"""
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
  const scrollers = Array.from(document.querySelectorAll('*')).filter(e => {
    const cs = getComputedStyle(e);
    return /auto|scroll/.test(cs.overflowY) && e.scrollHeight > e.clientHeight + 40;
  }).map(e => ({ tag: e.tagName, cls: String(e.className).slice(0, 80),
                 sh: e.scrollHeight, ch: e.clientHeight, st: Math.round(e.scrollTop),
                 r: rect(e) })).slice(0, 12);
  // 正文候选：包含长文本的块
  const bodies = Array.from(document.querySelectorAll('article,[class*=doc-content],[class*=doc-body],[class*=editor],[class*=reader],[class*=markdown]'))
    .filter(vis).map(e => ({ tag: e.tagName, cls: String(e.className).slice(0, 90),
                             len: (e.innerText || '').length, r: rect(e) })).slice(0, 10);
  return {
    url: location.href,
    title: document.title,
    bodyTextLen: (document.body.innerText || '').length,
    scrollers: scrollers,
    bodies: bodies,
    docRootCandidates: Array.from(document.querySelectorAll('[class*=doc-view],[class*=doc-detail],[class*=doc-page]'))
      .filter(vis).map(e => ({ cls: String(e.className).slice(0, 90), r: rect(e) })).slice(0, 8)
  };
})()"""

print(json.dumps(U.eval_in_iframe(JS), ensure_ascii=False, indent=1)[:4000])
