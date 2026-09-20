#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""点确定后找「确认允许完全访问？」确认框；并检查权限选择器。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402
import cdp as C               # noqa: E402

TARGET = "Array.from(document.querySelectorAll('.wb-modal button'))" \
         ".find(b => (b.innerText||'').trim() === '确定')"

FIND_CONFIRM = """(()=>{
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const all = Array.from(document.querySelectorAll('div,section,article')).filter(vis)
    .filter(e => (e.innerText||'').indexOf('确认允许完全访问') >= 0)
    .sort((a,b)=>a.querySelectorAll('*').length-b.querySelectorAll('*').length);
  const box = all[0];
  return {found: !!box,
          count: all.length,
          cls: box ? String(box.className).slice(0,120) : null,
          txt: box ? (box.innerText||'').replace(/\\s+/g,' ').slice(0,300) : null,
          buttons: box ? Array.from(box.querySelectorAll('button')).map(b=>({t:(b.innerText||'').trim().slice(0,20),cls:String(b.className).slice(0,60)})) : null,
          allModals: Array.from(document.querySelectorAll('.wb-modal')).map(m=>({cls:String(m.className).slice(0,80),
            t:(m.innerText||'').replace(/\\s+/g,' ').slice(0,120)}))};
})()"""

PERM_SEL = """(()=>{
  const m = document.querySelector('.wb-modal');
  if (!m) return {err:'no modal'};
  const b = Array.from(m.querySelectorAll('button')).find(x=>/完全访问|默认权限/.test(x.innerText||''));
  if (!b) return {err:'no perm btn'};
  const r = b.getBoundingClientRect();
  return {t:(b.innerText||'').trim(), cls:String(b.className).slice(0,100),
          x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2)};
})()"""


def main():
    cdp, _ = C.connect()
    try:
        # 先看权限选择器
        print("permBtn:", json.dumps(U.js(PERM_SEL), ensure_ascii=False))

        rect = cdp.evaluate("(function(){var e=%s;var r=e.getBoundingClientRect();"
                            "return{x:r.left+r.width/2,y:r.top+r.height/2};})()" % TARGET, timeout=20)
        x, y = rect["x"], rect["y"]
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "button": "none"})
        time.sleep(0.2)
        cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y,
                                              "button": "left", "buttons": 1, "clickCount": 1})
        time.sleep(0.12)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y,
                                              "button": "left", "buttons": 0, "clickCount": 1})
        time.sleep(1.2)
    finally:
        cdp.close()

    print("\nconfirm:", json.dumps(U.js(FIND_CONFIRM), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
