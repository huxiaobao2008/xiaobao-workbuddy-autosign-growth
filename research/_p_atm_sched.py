#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打开执行频率选择器，dump 结构与选项。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402

TRIG = "document.querySelector('.automation-editor-modal .atm-schedule-trigger')"


def main():
    r = U.mouse_click(TRIG)
    print("clickTrig:", json.dumps(r, ensure_ascii=False))
    time.sleep(1.5)
    r = U.js("""(()=>{
      const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
      // 找新增的浮层
      const pops = Array.from(document.querySelectorAll('[class*=popover],[class*=dropdown],[class*=panel],[class*=picker],[class*=schedule]'))
        .filter(vis).filter(e => !e.closest('.automation-editor-modal'));
      const rect = b => { const r = b.getBoundingClientRect();
        return [Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)]; };
      return {
        pops: pops.map(p=>({cls:String(p.className).slice(0,100), r:rect(p),
          t:(p.innerText||'').replace(/\\s+/g,' ').slice(0,400)})),
        inputs: Array.from(document.querySelectorAll('input')).filter(vis)
          .filter(i=>!i.closest('.automation-editor-modal') || /date|time|atm/i.test(i.className))
          .map(i=>({cls:String(i.className).slice(0,80), type:i.type, ph:i.placeholder,
                    v:i.value, r:rect(i)})),
        buttonsOut: Array.from(document.querySelectorAll('button')).filter(vis)
          .filter(b=>!b.closest('.automation-editor-modal'))
          .map(b=>({t:(b.innerText||'').replace(/\\s+/g,' ').trim().slice(0,30),
                    cls:String(b.className).slice(0,70), r:rect(b)})).slice(0,40)
      };
    })()""")
    print(json.dumps(r, ensure_ascii=False, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
