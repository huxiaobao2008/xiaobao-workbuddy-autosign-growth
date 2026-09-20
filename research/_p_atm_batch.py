#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""点「批量管理」并 dump 出现的复选框与按钮。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402

BATCH = "Array.from(document.querySelectorAll('.automation-main-page button'))" \
        ".find(b => /批量管理/.test(b.innerText||''))"


def main():
    print("click:", json.dumps(U.mouse_click(BATCH), ensure_ascii=False))
    time.sleep(1.5)
    print(json.dumps(U.js(r"""(()=>{
      const vis = el => { const r = el.getBoundingClientRect(); return r.width > 4 && r.height > 4; };
      const rect = e => { const r = e.getBoundingClientRect();
        return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
      return {
        txt: (document.querySelector('.automation-main-page')||{}).innerText.replace(/\s+/g,' ').slice(0,400),
        checkboxes: Array.from(document.querySelectorAll('.automation-main-page input[type=checkbox],.automation-main-page [class*=checkbox]'))
          .filter(vis).map(c=>({cls:String(c.className).slice(0,70), r:rect(c)})),
        buttons: Array.from(document.querySelectorAll('.automation-main-page button')).filter(vis)
          .map(b=>({t:(b.innerText||'').replace(/\s+/g,' ').trim().slice(0,20),
                    cls:String(b.className).slice(0,70), r:rect(b)})).slice(0,30)
      };
    })()"""), ensure_ascii=False, indent=1)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
