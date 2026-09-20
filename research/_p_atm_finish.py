#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""关浮层 → 点确定 → 若出权限确认框则改为默认权限 → 再点确定 → 校验列表。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402

OK_BTN = ("Array.from(document.querySelectorAll('.automation-editor-modal button'))"
          ".find(b => (b.innerText||'').trim() === '确定')")
FALLBACK = "document.querySelector('.automation-permission-confirm__fallback-link')"
CF_CB = "document.querySelector('.automation-permission-confirm__checkbox')"
CF_OK = ("Array.from(document.querySelectorAll('.automation-permission-confirm__dialog button'))"
         ".find(b => /确认创建/.test(b.innerText||''))")


def st():
    return U.js(r"""(()=>({
      editor: !!document.querySelector('.automation-editor-modal'),
      confirm: !!document.querySelector('.automation-permission-confirm__dialog'),
      errs: Array.from(document.querySelectorAll('.automation-workspace__error')).map(e=>(e.innerText||'').replace(/\s+/g,' ').trim()),
      toasts: Array.from(document.querySelectorAll('[class*=toast],[class*=wb-message]')).filter(e=>(e.innerText||'').trim()).map(e=>(e.innerText||'').replace(/\s+/g,' ').slice(0,120))
    }))()""")


def main():
    # 关掉频率浮层
    U.js("(async()=>{document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));await sleep(700);return 1;})()")
    time.sleep(0.8)
    print("popoverClosed:", U.js("(()=>!document.querySelector('.atm-frequency-popover'))()"))

    print("clickOK:", json.dumps(U.mouse_click(OK_BTN), ensure_ascii=False))
    time.sleep(2.0)
    s = st()
    print("afterOK:", json.dumps(s, ensure_ascii=False))

    if s.get("confirm"):
        print("fallback:", json.dumps(U.mouse_click(FALLBACK), ensure_ascii=False))
        time.sleep(2.0)
        s2 = st()
        print("afterFallback:", json.dumps(s2, ensure_ascii=False))
        if s2.get("editor"):
            print("clickOK2:", json.dumps(U.mouse_click(OK_BTN), ensure_ascii=False))
            time.sleep(3.0)
            s3 = st()
            print("afterOK2:", json.dumps(s3, ensure_ascii=False))
            if s3.get("confirm"):
                print("checkCb:", json.dumps(U.mouse_click(CF_CB), ensure_ascii=False))
                time.sleep(0.8)
                print("clickCreate:", json.dumps(U.mouse_click(CF_OK), ensure_ascii=False))
                time.sleep(3.0)
                print("final:", json.dumps(st(), ensure_ascii=False))

    time.sleep(2.0)
    print("list:", json.dumps(U.js(r"""(()=>{
      const p = document.querySelector('.automation-main-page');
      return p ? p.innerText.replace(/\s+/g,' ').slice(0,400) : null;
    })()"""), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
