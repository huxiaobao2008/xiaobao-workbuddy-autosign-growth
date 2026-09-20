#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专家页：找「召唤」按钮 → 点第一个 → 观察结果（是否新建会话/计分）。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402

SUMMARY = r"""(()=>{
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 4 && r.height > 4; };
  const rect = e => { const r = e.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  const callBtns = Array.from(document.querySelectorAll('button')).filter(vis)
    .filter(b => /召唤/.test(b.innerText || ''))
    .map(b => ({ t: (b.innerText||'').replace(/\s+/g,' ').trim().slice(0,20),
                 cls: String(b.className).slice(0, 80), r: rect(b) }));
  return { tabActive: Array.from(document.querySelectorAll('.conversation-list-tab-button.active'))
             .map(e => (e.innerText||'').replace(/\s+/g,' ').trim()),
           mainTxt: (document.querySelector('.main-content') || document.body).innerText
             .replace(/\s+/g,' ').slice(0, 300),
           callBtns: callBtns.slice(0, 8) };
})()"""

FIRST_CALL = ("Array.from(document.querySelectorAll('button')).filter(b => {"
              " const r = b.getBoundingClientRect();"
              " return r.width > 4 && r.height > 4 && /召唤/.test(b.innerText||''); })[0]")


def main():
    print("before:", json.dumps(U.js(SUMMARY), ensure_ascii=False, indent=1)[:1800])
    print("click:", json.dumps(U.mouse_click(FIRST_CALL), ensure_ascii=False))
    time.sleep(4.0)
    print("after:", json.dumps(U.js(
        "(()=>({url:location.href.slice(0,140),"
        " txt:(document.body.innerText||'').replace(/\\s+/g,' ').slice(0,700),"
        " convoTitles:Array.from(document.querySelectorAll('.conversation-item')).map(e=>(e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,40)),"
        " chips:Array.from(document.querySelectorAll('[class*=phrase-content-wrapper],[class*=expert-chip],[class*=agent-chip]')).map(e=>(e.innerText||'').trim().slice(0,30))}))()"),
        ensure_ascii=False, indent=1)[:2500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
