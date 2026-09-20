#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量管理里按名字勾选 → 删除 → 确认 → 退出。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402

NAME = sys.argv[1] if len(sys.argv) > 1 else "自动刷任务测试D"

BATCH = ("Array.from(document.querySelectorAll('.automation-main-page button'))"
         ".find(b => /批量管理/.test(b.innerText||''))")
EXIT = ("Array.from(document.querySelectorAll('.automation-main-page button'))"
        ".find(b => /退出管理/.test(b.innerText||''))")
DEL = ("Array.from(document.querySelectorAll('.automation-main-page button'))"
       ".find(b => (b.innerText||'').trim() === '删除')")
CB = ("Array.from(document.querySelectorAll('div.atm-row'))"
      ".filter(r => ((r.querySelector('.atm-row-name')||{}).innerText||'').trim() === %s)[0]"
      ".querySelector('.atm-row-checkbox')" % json.dumps(NAME))


def state():
    return U.js("(()=>({txt:(document.querySelector('.automation-main-page')||{}).innerText"
                ".replace(/\\s+/g,' ').slice(0,300),"
                "modal:!!document.querySelector('.wb-modal')}))()")


def main():
    if not U.js("(()=>!!document.querySelector('.automation-main-page'))()"):
        U.js("(async()=>{clickSidebar('定时任务');await sleep(3000);return 1;})()")
        time.sleep(0.5)
    # 进批量管理（若不在）
    if not U.js("(()=>/已选择/.test((document.querySelector('.automation-main-page')||{}).innerText||''))()"):
        print("batch:", json.dumps(U.mouse_click(BATCH), ensure_ascii=False))
        time.sleep(1.4)
    print("state:", json.dumps(state(), ensure_ascii=False))
    print("cb:", json.dumps(U.mouse_click(CB), ensure_ascii=False))
    time.sleep(1.0)
    print("afterCheck:", json.dumps(state(), ensure_ascii=False))
    print("del:", json.dumps(U.mouse_click(DEL), ensure_ascii=False))
    time.sleep(1.6)
    # 可能的确认框
    s = U.js(r"""(()=>{
      const m = document.querySelector('.wb-modal');
      if (!m) return {modal:false};
      return {modal:true, txt:(m.innerText||'').replace(/\s+/g,' ').slice(0,200),
        btns: Array.from(m.querySelectorAll('button')).map(b=>({t:(b.innerText||'').trim().slice(0,16),cls:String(b.className).slice(0,60)}))};
    })()""")
    print("confirmModal:", json.dumps(s, ensure_ascii=False))
    if s.get("modal"):
        r = U.mouse_click("Array.from(document.querySelectorAll('.wb-modal button'))"
                          ".filter(b => /确认|删除/.test(b.innerText||'') "
                          "&& /primary|danger/.test(b.className))"
                          ".sort((a,b)=>/danger/.test(b.className)-/danger/.test(a.className))[0]")
        print("confirmDel:", json.dumps(r, ensure_ascii=False))
        time.sleep(2.2)
    print("afterDel:", json.dumps(state(), ensure_ascii=False))
    print("exit:", json.dumps(U.mouse_click(EXIT), ensure_ascii=False))
    time.sleep(1.2)
    print("final:", json.dumps(state(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
