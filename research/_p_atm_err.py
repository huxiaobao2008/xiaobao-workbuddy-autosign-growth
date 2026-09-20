#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""捕获点击「确定」瞬间的控制台错误与未捕获异常。"""
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

log = []


def main():
    cdp, _ = C.connect()
    try:
        cdp.handlers["Runtime.consoleAPICalled"] = lambda p: log.append(
            "[%s] %s" % (p.get("type"), " ".join(
                str(a.get("value", a.get("description", "")))[:200] for a in p.get("args", []))))
        cdp.handlers["Runtime.exceptionThrown"] = lambda p: log.append(
            "[EXC] " + json.dumps(p.get("exceptionDetails", {}), ensure_ascii=False)[:400])
        cdp.call("Runtime.enable", {}, timeout=15)

        # 按钮自身信息 + React props
        info = U.js("""(()=>{
          const b = %s;
          const k = Object.keys(b).find(x=>x.startsWith('__reactProps'));
          const p = k ? b[k] : null;
          const fk = Object.keys(b).find(x=>x.startsWith('__reactFiber'));
          const fib = fk ? b[fk] : null;
          return {type:b.getAttribute('type'), inForm:!!b.closest('form'),
                  hasOnClick: !!(p && p.onClick), propKeys: p?Object.keys(p).slice(0,20):null,
                  onClickSrc: p && p.onClick ? String(p.onClick).slice(0,400) : null,
                  fiberTag: fib ? fib.tag : null};
        })()""" % TARGET)
        print("btnInfo:", json.dumps(info, ensure_ascii=False, indent=1))

        rect = cdp.evaluate("(function(){var e=%s;var r=e.getBoundingClientRect();"
                            "return{x:r.left+r.width/2,y:r.top+r.height/2};})()" % TARGET, timeout=20)
        x, y = rect["x"], rect["y"]
        log.clear()
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "button": "none"})
        time.sleep(0.2)
        cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y,
                                              "button": "left", "buttons": 1, "clickCount": 1})
        time.sleep(0.12)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y,
                                              "button": "left", "buttons": 0, "clickCount": 1})
        # 反复 evaluate 以抽干事件
        for _ in range(8):
            time.sleep(0.6)
            U.js("1")
    finally:
        cdp.close()

    print("\n--- 点击期间日志 ---")
    for x in log:
        print(x[:300])
    print("\nopen:", U.js("(()=>!!document.querySelector('.wb-modal'))()"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
