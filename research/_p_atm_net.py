#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""监听点击「确定」后是否发出创建请求（判定 click 是否触发 onSubmit）。"""
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402
import cdp as C               # noqa: E402

TARGET = "Array.from(document.querySelectorAll('.wb-modal button'))" \
         ".find(b => (b.innerText||'').trim() === '确定')"

reqs = []


def main():
    cdp, _ = C.connect()
    try:
        def on_req(params):
            r = params.get("request", {})
            u = r.get("url", "")
            if not any(s in u for s in ("automation", "task", "schedule", "growth", "api")):
                return
            reqs.append("%s %s" % (r.get("method"), u[:170]))

        def on_resp(params):
            p = params.get("response", {})
            if any(s in p.get("url", "") for s in ("automation", "task", "schedule")):
                reqs.append("  <- %s %s" % (p.get("status"), p.get("url")[:150]))

        cdp.handlers["Network.requestWillBeSent"] = on_req
        cdp.handlers["Network.responseReceived"] = on_resp
        cdp.handlers["Runtime.consoleAPICalled"] = lambda p: reqs.append(
            "  [console.%s] %s" % (p.get("type"), " ".join(
                str(a.get("value", a.get("description", "")))[:120] for a in p.get("args", []))))
        cdp.call("Network.enable", {}, timeout=15)
        cdp.call("Runtime.enable", {}, timeout=15)

        # 点确定前的状态
        st0 = U.js("(()=>{const m=document.querySelector('.wb-modal');"
                   "return m?{modal:true}:{modal:false};})()")
        print("before:", json.dumps(st0, ensure_ascii=False))

        r = U.mouse_click(TARGET)
        print("click:", json.dumps(r, ensure_ascii=False))

        for i in range(12):
            time.sleep(1.0)
            st = U.js("(()=>({modal:!!document.querySelector('.wb-modal'),"
                      "toasts:Array.from(document.querySelectorAll('[class*=toast],[class*=wb-message]'))"
                      ".filter(e=>(e.innerText||'').trim()).map(e=>(e.innerText||'').replace(/\\s+/g,' ').slice(0,90))}))()")
            print("t+%ds %s" % (i + 1, json.dumps(st, ensure_ascii=False)))
            if not st.get("modal"):
                print(">>> modal closed at t+%ds" % (i + 1))
                break

        print("\n--- 网络 ---")
        for x in reqs[-40:]:
            print(x)
    finally:
        cdp.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
