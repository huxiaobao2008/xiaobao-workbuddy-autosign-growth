#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""点权限选择器后，全页搜「默认权限」相关浮层。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402
import cdp as C               # noqa: E402

PERM_BTN = "Array.from(document.querySelectorAll('.wb-modal button'))" \
           ".find(x=>/完全访问|默认权限/.test(x.innerText||''))"

SEARCH = """(()=>{
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const hits = Array.from(document.querySelectorAll('*')).filter(vis)
    .filter(e => (e.innerText||'').indexOf('默认权限') >= 0 || (e.innerText||'').indexOf('安全沙箱') >= 0)
    .sort((a,b)=>a.querySelectorAll('*').length-b.querySelectorAll('*').length);
  const box = hits[0];
  return {n:hits.length,
    cls: box?String(box.className).slice(0,110):null,
    txt: box?(box.innerText||'').replace(/\\s+/g,' ').slice(0,300):null,
    items: box?Array.from(box.querySelectorAll('*')).filter(vis).filter(e=>e.children.length<=2 && (e.innerText||'').trim())
      .map(e=>({c:String(e.className).slice(0,60), t:(e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,50)})).slice(0,25):null};
})()"""


def main():
    print("before:", json.dumps(U.js(SEARCH), ensure_ascii=False)[:200])
    r = U.mouse_click(PERM_BTN)
    print("clicked:", json.dumps(r, ensure_ascii=False))
    time.sleep(1.6)
    print(json.dumps(U.js(SEARCH), ensure_ascii=False, indent=1))
    # 也 dump 整个 modal 的 html 片段（找 popover 容器）
    print("\n--- modal 内 popover/tooltip 类元素 ---")
    print(json.dumps(U.js("""(()=>{
      const m=document.querySelector('.wb-modal');
      return Array.from(m.querySelectorAll('[class*=popover],[class*=tooltip],[class*=dropdown],[class*=select]'))
        .map(e=>({c:String(e.className).slice(0,90),v:!!(e.getBoundingClientRect().width>8),
                  t:(e.innerText||'').replace(/\\s+/g,' ').slice(0,120)}));
    })()"""), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
