#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 MutationObserver 捕获点「确定」后新增的节点（找二次确认框）。"""
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
      window.__add = [];
      if (window.__obs) window.__obs.disconnect();
      window.__obs = new MutationObserver(muts => {
        muts.forEach(m => m.addedNodes.forEach(n => {
          if (n.nodeType !== 1) return;
          window.__add.push({cls:String(n.className||'').slice(0,110),
            t:(n.innerText||'').replace(/\\s+/g,' ').slice(0,180)});
        }));
      });
      window.__obs.observe(document.body, {childList:true, subtree:true});
      return 1;
    })()""")

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
        for _ in range(6):
            time.sleep(0.5)
            U.js("1")
    finally:
        cdp.close()

    r = U.js("(()=>({added:window.__add||[],open:!!document.querySelector('.wb-modal')}))()")
    print(json.dumps(r, ensure_ascii=False, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
