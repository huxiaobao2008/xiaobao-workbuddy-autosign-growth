#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""灵感案例：开卡 → 做同款 → 观察是否新建会话/填入输入框。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402
import ui_tasks as T          # noqa: E402

HOME = ("Array.from(document.querySelectorAll('.conversation-list-tab-button'))"
        ".find(e => /新建任务/.test(e.innerText||''))")


def snap(tag):
    r = U.js(r"""(()=>({
      modal: !!document.querySelector('.dc-detail-modal'),
      modalBtns: Array.from(document.querySelectorAll('.dc-detail-modal button'))
        .filter(b=>(b.innerText||'').trim()).map(b=>(b.innerText||'').replace(/\s+/g,' ').trim().slice(0,20)),
      input: (document.querySelector('[contenteditable=true]')||{}).innerText||null,
      chips: Array.from(document.querySelectorAll('[class*=phrase-content-wrapper]')).map(e=>(e.innerText||'').trim().slice(0,40)),
      convo: Array.from(document.querySelectorAll('.conversation-item')).map(e=>(e.innerText||'').replace(/\s+/g,' ').trim().slice(0,44)),
      sendDis: (()=>{const b=document.querySelector('button.cr-send-button');return b?!!b.disabled:null;})()
    }))()""")
    print("[%s] %s" % (tag, json.dumps(r, ensure_ascii=False)[:800]))
    return r


def main():
    T.dismiss_overlays()
    if not U.js("(()=>document.querySelectorAll('.wb-related-playbooks__card').length>0)()"):
        U.mouse_click(HOME)
        time.sleep(3.0)
    print("card:", json.dumps(U.mouse_click("document.querySelectorAll('.wb-related-playbooks__card')[0]"),
                              ensure_ascii=False))
    time.sleep(2.5)
    snap("card_open")
    print("same:", json.dumps(U.mouse_click(
        "Array.from(document.querySelectorAll('.dc-detail-modal button')).find(b=>/做同款/.test(b.innerText||''))"),
        ensure_ascii=False))
    for i in range(4):
        time.sleep(1.5)
        snap("t+%.1f" % ((i + 1) * 1.5))
    return 0


if __name__ == "__main__":
    sys.exit(main())
