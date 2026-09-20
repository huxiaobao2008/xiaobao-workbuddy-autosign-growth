#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打开日期选择器并 dump 日历面板。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402

DATE_TRIG = "document.querySelector('.atm-schedule-date-input .wb-datepicker-trigger')"


def main():
    # 若频率浮层已关，先打开（这里假定还开着；否则先点 trigger）
    if not U.js("(()=>!!document.querySelector('.atm-frequency-popover'))()"):
        U.mouse_click("document.querySelector('.automation-editor-modal .atm-schedule-trigger')")
        time.sleep(1.5)
    r = U.mouse_click(DATE_TRIG)
    print("clickDate:", json.dumps(r, ensure_ascii=False))
    time.sleep(1.5)
    print(json.dumps(U.js(r"""(()=>{
      const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
      const p = Array.from(document.querySelectorAll('.wb-datepicker-panel,.wb-picker-panel,[class*=datepicker-panel]')).filter(vis)[0];
      if (!p) return { err: 'no date panel' };
      const rect = e => { const r = e.getBoundingClientRect();
        return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
      return { cls: String(p.className).slice(0,90),
               txt: (p.innerText||'').replace(/\s+/g,' ').slice(0,300),
               cells: Array.from(p.querySelectorAll('td,button,div[class*=cell]')).filter(vis)
                 .map(c=>({t:(c.innerText||'').trim().slice(0,8), cls:String(c.className).slice(0,70), r:rect(c)}))
                 .filter(c=>c.t).slice(0,50) };
    })()"""), ensure_ascii=False, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
