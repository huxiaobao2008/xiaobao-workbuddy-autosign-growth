#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在「确定」按钮上挂事件监听，确认 CDP 点击是否真的派发到该按钮。"""
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
    # 1) 挂监听
    r = U.js("""(()=>{
      const b = %s;
      if(!b) return {err:'no btn'};
      window.__wbclk = [];
      ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t=>{
        b.addEventListener(t, e=>{
          window.__wbclk.push({t:t, trusted:e.isTrusted,
            x:Math.round(e.clientX), y:Math.round(e.clientY),
            def:e.defaultPrevented, btns:e.buttons});
        }, true);
      });
      // 同时监听 overlay 上的点击
      window.__wbcov = [];
      const ov = document.querySelector('.wb-modal__overlay');
      if (ov) ov.addEventListener('click', e=>{
        window.__wbcov.push({t:'overlay-click', trusted:e.isTrusted,
          sx:Math.round(e.clientX), sy:Math.round(e.clientY)});
      }, true);
      const m = document.querySelector('.wb-modal');
      window.__wbmod = [];
      m.addEventListener('click', e=>{
        window.__wbmod.push({t:'modal-click', trusted:e.isTrusted,
          target:String(e.target.className).slice(0,60)});
      }, true);
      return {ok:true};
    })()""" % TARGET)
    print("attach:", json.dumps(r, ensure_ascii=False))

    cdp, _ = C.connect()
    try:
        rect = cdp.evaluate("(function(){var e=%s;var r=e.getBoundingClientRect();"
                            "return{x:r.left+r.width/2,y:r.top+r.height/2};})()" % TARGET, timeout=20)
        print("rect:", rect)
        x, y = rect["x"], rect["y"]
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "button": "none"})
        time.sleep(0.2)
        cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y,
                                              "button": "left", "buttons": 1, "clickCount": 1})
        time.sleep(0.12)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y,
                                              "button": "left", "buttons": 0, "clickCount": 1})
        time.sleep(1.0)
    finally:
        cdp.close()

    r = U.js("(()=>({btn:window.__wbclk||null,overlay:window.__wbcov||null,"
             "modal:window.__wbmod||null,stillOpen:!!document.querySelector('.wb-modal')}))()")
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
