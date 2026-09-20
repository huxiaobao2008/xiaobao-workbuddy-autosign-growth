#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""灵感：找案例卡片 → 点第一个 → 观察结果。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402
import ui_tasks as T          # noqa: E402

FIND = r"""(()=>{
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const rect = e => { const r = e.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  // 标题里带「案例」的区块
  const secTitle = Array.from(document.querySelectorAll('*')).filter(vis)
    .find(e => /最佳实践案例/.test(e.innerText || '') && (e.innerText||'').length < 30);
  // 卡片：含长文本、结构不深、位于页面下半部
  const cards = Array.from(document.querySelectorAll('div,[class*=card]')).filter(vis)
    .filter(e => { const r = e.getBoundingClientRect();
      return r.top > 380 && r.height > 80 && r.height < 320 && r.width > 120 && r.width < 320; })
    .map(e => ({ cls: String(e.className).slice(0, 70),
                 t: (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 40),
                 kids: e.querySelectorAll('*').length, r: rect(e) }))
    .filter(c => c.t).slice(0, 12);
  return { secFound: !!secTitle, secTxt: secTitle ? (secTitle.innerText||'').replace(/\s+/g,' ').slice(0,60) : null,
           cards: cards };
})()"""


def main():
    print("find:", json.dumps(U.js(FIND), ensure_ascii=False, indent=1)[:2500])
    # 点第一个最小卡片
    click = ("Array.from(document.querySelectorAll('div')).filter(e => {"
             " const r = e.getBoundingClientRect();"
             " return r.top > 380 && r.height > 80 && r.height < 320 && r.width > 120 && r.width < 320"
             " && (e.innerText||'').trim() && e.querySelectorAll('*').length > 2; })"
             ".sort((a,b)=>a.querySelectorAll('*').length-b.querySelectorAll('*').length)[0]")
    print("click:", json.dumps(U.mouse_click(click), ensure_ascii=False))
    time.sleep(3.0)
    print("after:", json.dumps(U.js(
        "(()=>({url:location.href.slice(0,120),"
        " txt:(document.body.innerText||'').replace(/\\s+/g,' ').slice(0,600),"
        " modals:Array.from(document.querySelectorAll('.wb-modal,[role=dialog]')).map(m=>(m.innerText||'').replace(/\\s+/g,' ').slice(0,150)),"
        " input:(document.querySelector('[contenteditable=true]')||{}).innerText||null}))()"),
        ensure_ascii=False, indent=1)[:2500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
