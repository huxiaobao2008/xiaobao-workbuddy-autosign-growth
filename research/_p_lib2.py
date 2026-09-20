#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打开资料库里的《WorkBuddy资料库介绍》文档并 dump 阅读页。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_tasks as T          # noqa: E402
import ui_driver as U         # noqa: E402

CARD = ("Array.from(document.querySelectorAll('*')).filter(e => e.children.length <= 4 "
        "&& /WorkBuddy\\s*资料库介绍/.test(e.innerText || ''))"
        ".sort((a,b)=>a.querySelectorAll('*').length-b.querySelectorAll('*').length)[0]")


def main():
    # 确保在资料库
    U.js("(async()=>{const f=(t)=>{const b=Array.from(document.querySelectorAll('.conversation-list-tab-button'))"
         ".find(e=>(e.innerText||'').replace(/\\s+/g,'').replace('更多','')===t);if(b)b.click();return !!b;};"
         "f('资料库');await sleep(3500);return 1;})()")
    time.sleep(0.5)
    print("iframes:", json.dumps(U.js("(()=>Array.from(document.querySelectorAll('iframe,webview')).map(f=>({tag:f.tagName,src:(f.src||'').slice(0,120),cls:String(f.className).slice(0,60)})))()"), ensure_ascii=False))
    print("card:", json.dumps(U.js("(()=>{const c=%s;return c?{tag:c.tagName,cls:String(c.className).slice(0,90),t:(c.innerText||'').replace(/\\s+/g,' ').slice(0,80)}:'none';})()" % CARD), ensure_ascii=False))
    print("click:", json.dumps(U.mouse_click(CARD), ensure_ascii=False))
    time.sleep(4.0)
    print(json.dumps(U.js(r"""(()=>{
      const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
      return {
        iframes: Array.from(document.querySelectorAll('iframe,webview')).map(f=>({src:(f.src||'').slice(0,150)})),
        txt: (document.body.innerText||'').replace(/\s+/g,' ').slice(0,900),
        btns: Array.from(document.querySelectorAll('button')).filter(vis)
          .map(b=>(b.innerText||'').replace(/\s+/g,' ').trim()).filter(Boolean).slice(0,25)
      };
    })()"""), ensure_ascii=False, indent=1)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
