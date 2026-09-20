#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""点击「确定」后枚举所有 overlay/dialog，寻找权限确认层。"""
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

SCAN = """(()=>{
  const vis = el => { const r = el.getBoundingClientRect();
    return r.width > 8 && r.height > 8 && getComputedStyle(el).visibility !== 'hidden'
      && getComputedStyle(el).display !== 'none'; };
  const sel = '[class*=overlay],[class*=modal],[class*=dialog],[class*=popover],[class*=popup],[role=dialog],[class*=confirm],[class*=permission]';
  return Array.from(document.querySelectorAll(sel)).filter(vis)
    .map(e=>{const r=e.getBoundingClientRect();
      return {cls:String(e.className).slice(0,110),
              xy:[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)],
              t:(e.innerText||'').replace(/\\s+/g,' ').slice(0,140)};});
})()"""


def main():
    cdp, _ = C.connect()
    try:
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
        # 立刻 + 之后分别扫描
        for t in (0.3, 1.5, 3.0):
            time.sleep(t)
            print("=== t+%.1fs ===" % t)
            print(json.dumps(U.js(SCAN), ensure_ascii=False, indent=1)[:3000])
    finally:
        cdp.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
