#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对照实验：CDP 真鼠标点击「取消」是否能关闭对话框（验证 CDP 点击本身是否有效）。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_tasks as T          # noqa: E402
import ui_driver as U         # noqa: E402


def step(tag, obj):
    print("[%s] %s" % (tag, json.dumps(obj, ensure_ascii=False)[:400]))
    sys.stdout.flush()


def state():
    return U.js("(()=>({modal:!!document.querySelector('.wb-modal'),"
                "dpr:window.devicePixelRatio,"
                "iw:window.innerWidth,ih:window.innerHeight,"
                "zoom:(window.outerWidth/window.innerWidth).toFixed(3)}))()")


def main():
    U.js("(async()=>{for(let i=0;i<3;i++)document.dispatchEvent("
         "new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return 1;})()")
    time.sleep(1.2)
    step("before", state())

    r = T._js_block(T.ATM_OPEN2, timeout=120)
    step("open", {"opened": r.get("opened")})
    if not r.get("opened"):
        return 1
    step("opened_state", state())

    # 按钮几何
    geo = U.js("(()=>{const m=document.querySelector('.wb-modal');"
               "const b=Array.from(m.querySelectorAll('button')).find(x=>(x.innerText||'').trim()==='取消');"
               "if(!b)return{err:'no cancel'};"
               "const r=b.getBoundingClientRect();"
               "return{x:Math.round(r.left),y:Math.round(r.top),w:Math.round(r.width),h:Math.round(r.height)};})()")
    step("cancel_rect", geo)

    # CDP 点取消
    r = U.mouse_click("Array.from(document.querySelectorAll('.wb-modal button'))"
                      ".find(b => (b.innerText||'').trim() === '取消')")
    step("mouseCancel", r)
    time.sleep(2.0)
    step("after_cdp_cancel", state())

    # 若还开着，用合成事件点取消
    if U.js("(()=>!!document.querySelector('.wb-modal'))()"):
        r = U.js("(async()=>{const m=document.querySelector('.wb-modal');"
                 "const b=Array.from(m.querySelectorAll('button')).find(x=>(x.innerText||'').trim()==='取消');"
                 "if(!b)return{err:'no cancel'}; b.click(); await sleep(1500);"
                 "return{done:true};})()")
        step("syntheticCancel", r)
        time.sleep(1.5)
        step("after_synthetic_cancel", state())
    return 0


if __name__ == "__main__":
    sys.exit(main())
