#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""点击权限选择器 → dump 选项 → 选「默认权限」。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402

PERM_BTN = "Array.from(document.querySelectorAll('.wb-modal button'))" \
           ".find(x=>/完全访问|默认权限/.test(x.innerText||''))"


def main():
    r = U.mouse_click(PERM_BTN)
    print("clickPerm:", json.dumps(r, ensure_ascii=False))
    time.sleep(1.5)
    r = U.js("""(()=>{
      const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
      const pops = Array.from(document.querySelectorAll('[class*=popover],[class*=dropdown],[class*=menu],[role=menu]'))
        .filter(vis);
      return {n:pops.length,
        pops: pops.map(p=>({cls:String(p.className).slice(0,90),
          t:(p.innerText||'').replace(/\\s+/g,' ').slice(0,220),
          items: Array.from(p.querySelectorAll('button,[role=menuitem],[class*=item]')).map(i=>(i.innerText||'').replace(/\\s+/g,' ').trim().slice(0,40)).filter(Boolean).slice(0,10)}))};
    })()""")
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
