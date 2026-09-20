#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""点击灵感案例卡片并观察结果。"""
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
CARD0 = "document.querySelectorAll('.wb-related-playbooks__card')[0]"


def main():
    T.dismiss_overlays()
    if not U.js("(()=>document.querySelectorAll('.wb-related-playbooks__card').length > 0)()"):
        U.mouse_click(HOME)
        time.sleep(3.0)
    print("cards:", U.js("(()=>Array.from(document.querySelectorAll('.wb-related-playbooks__card'))"
                         ".map(e=>(e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,30)))()"))
    print("click:", json.dumps(U.mouse_click(CARD0), ensure_ascii=False))
    time.sleep(3.5)
    print("after:", json.dumps(U.js(r"""(()=>({
      txt:(document.body.innerText||'').replace(/\s+/g,' ').slice(0,500),
      modals:Array.from(document.querySelectorAll('.wb-modal,[role=dialog],[class*=drawer]')).map(m=>(m.innerText||'').replace(/\s+/g,' ').slice(0,180)),
      input:(document.querySelector('[contenteditable=true]')||{}).innerText||null,
      url:location.href.slice(0,110)
    }))()"""), ensure_ascii=False, indent=1)[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
