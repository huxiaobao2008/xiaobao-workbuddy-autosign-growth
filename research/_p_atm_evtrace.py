#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 document 捕获阶段记录全部鼠标事件的真实 target。"""
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


def main():
    U.js("""(()=>{
      window.__ev = [];
      ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t=>{
        document.addEventListener(t, e=>{
          const t2 = e.target;
          const rec = {ev:t, trusted:e.isTrusted,
            tgt: t2 ? (t2.tagName + '.' + String(t2.className).slice(0,50)) : null,
            x:Math.round(e.clientX), y:Math.round(e.clientY), def:e.defaultPrevented};
          // 是否是「确定」按钮或其子节点
          rec.onOk = !!(t2 && t2.closest && t2.closest('button.wb-button--primary'));
          window.__ev.push(rec);
        }, true);
      });
      return 1;
    })()""")

    cdp, _ = C.connect()
    try:
        rect = cdp.evaluate("(function(){var e=%s;var r=e.getBoundingClientRect();"
                            "return{x:r.left+r.width/2,y:r.top+r.height/2};})()" % TARGET, timeout=20)
        x, y = rect["x"], rect["y"]
        print("rect:", json.dumps(rect))
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "button": "none"})
        time.sleep(0.3)
        cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y,
                                              "button": "left", "buttons": 1, "clickCount": 1})
        time.sleep(0.15)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y,
                                              "button": "left", "buttons": 0, "clickCount": 1})
        time.sleep(1.0)
    finally:
        cdp.close()

    print(json.dumps(U.js("(()=>({ev:window.__ev||null,open:!!document.querySelector('.wb-modal')}))()"),
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
