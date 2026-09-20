#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dump atm-frequency-popover 完整结构。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402

JS = r"""(()=>{
  const p = document.querySelector('.atm-frequency-popover');
  if (!p) return { err: 'no popover' };
  const rect = e => { const r = e.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  return {
    txt: (p.innerText || '').replace(/\s+/g, ' ').slice(0, 300),
    btns: Array.from(p.querySelectorAll('button')).map(b => ({
      t: (b.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 30),
      cls: String(b.className).slice(0, 90),
      active: /active|selected|checked/.test(b.className),
      r: rect(b) })),
    inputs: Array.from(p.querySelectorAll('input')).map(i => ({
      cls: String(i.className).slice(0, 80), type: i.type, v: i.value,
      ph: i.placeholder, ro: i.readOnly, r: rect(i) })),
    selects: Array.from(p.querySelectorAll('[class*=select],[class*=picker],[class*=time]')).map(e => ({
      cls: String(e.className).slice(0, 80),
      t: (e.innerText || '').replace(/\s+/g, ' ').slice(0, 60), r: rect(e) })),
    html: p.outerHTML.slice(0, 1800)
  };
})()"""

print(json.dumps(U.js(JS), ensure_ascii=False, indent=1)[:5000])
