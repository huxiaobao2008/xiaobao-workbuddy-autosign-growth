#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Expert_lighthouse：召唤「腾讯轻量云专家」并观察授权/会话状态。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402

CALL = ("Array.from(document.querySelectorAll('button'))"
        ".filter(b => { const r = b.getBoundingClientRect();"
        " return r.width > 4 && r.height > 4 && /召唤/.test(b.innerText||''); })[0]")


def dump(tag):
    r = U.js(r"""(()=>({
      txt: (document.body.innerText||'').replace(/\s+/g,' ').slice(0, 800),
      convoTitles: Array.from(document.querySelectorAll('.conversation-item')).map(e=>(e.innerText||'').replace(/\s+/g,' ').trim().slice(0,40)),
      inputHint: (document.querySelector('[contenteditable=true]')||{}).innerText||null,
      authBtns: Array.from(document.querySelectorAll('button')).filter(b=>/授权|连接器|允许/.test(b.innerText||'')).map(b=>(b.innerText||'').trim().slice(0,20)).slice(0,10),
      chips: Array.from(document.querySelectorAll('[class*=phrase-content-wrapper]')).map(e=>(e.innerText||'').trim().slice(0,30))
    }))()""")
    print("[%s] %s" % (tag, json.dumps(r, ensure_ascii=False)[:1200]))
    return r


def main():
    dump("before")
    print("click:", json.dumps(U.mouse_click(CALL), ensure_ascii=False))
    time.sleep(4.0)
    dump("after_click")
    return 0


if __name__ == "__main__":
    sys.exit(main())
