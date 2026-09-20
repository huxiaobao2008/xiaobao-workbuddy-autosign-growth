#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 CDP 鼠标坐标是否命中：把鼠标移到 (x,y)，看 :hover 链落在谁身上。"""
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


def hover_report():
    return U.js("(()=>{const h=Array.from(document.querySelectorAll(':hover'));"
                "return h.map(e=>e.tagName+'.'+String(e.className).slice(0,50));})()")


def main():
    cdp, _ = C.connect()
    try:
        rect = cdp.evaluate("(function(){var e=%s;var r=e.getBoundingClientRect();"
                            "return{x:r.left+r.width/2,y:r.top+r.height/2,"
                            "l:Math.round(r.left),t:Math.round(r.top),"
                            "w:Math.round(r.width),h:Math.round(r.height)};})()" % TARGET, timeout=20)
        print("rect:", json.dumps(rect))
        for label, x, y in [("center", rect["x"], rect["y"])]:
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y,
                                                  "button": "none"}, timeout=15)
            time.sleep(0.5)
            print("%s (%s,%s) hover -> %s" % (label, round(x), round(y),
                                              json.dumps(hover_report(), ensure_ascii=False)))
    finally:
        cdp.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
