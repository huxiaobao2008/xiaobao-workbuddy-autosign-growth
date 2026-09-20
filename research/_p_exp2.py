#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自带导航：进专家中心 → 点第一个召唤 → dump。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402
import ui_tasks as T          # noqa: E402

TAB = ("Array.from(document.querySelectorAll('.conversation-list-tab-button'))"
       ".find(e => /专家/.test(e.innerText||''))")
CARD_TABS = r"""(()=>{
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 4 && r.height > 4; };
  const rect = e => { const r = e.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  return {
    ecCards: document.querySelectorAll('.ec-expert-card').length,
    summonBtns: document.querySelectorAll('.ec-card-summon-btn').length,
    topTabs: Array.from(document.querySelectorAll('[class*=ec-tab],[role=tab],button')).filter(vis)
      .filter(b => /^(专家|专家团|技能|连接器)$/.test((b.innerText||'').trim()))
      .map(b => ({ t: (b.innerText||'').trim(), cls: String(b.className).slice(0, 70), r: rect(b) }))
  };
})()"""


def main():
    T.dismiss_overlays()
    print("clickTab:", json.dumps(U.mouse_click(TAB), ensure_ascii=False))
    time.sleep(3.0)
    print("state1:", json.dumps(U.js(CARD_TABS), ensure_ascii=False, indent=1)[:1200])
    if not U.js("(()=>document.querySelectorAll('.ec-card-summon-btn').length)()"):
        print("no summon btn; dump:", json.dumps(U.js(
            "(()=>({txt:(document.querySelector('.main-content')||document.body).innerText.replace(/\\s+/g,' ').slice(0,300)}))()"),
            ensure_ascii=False)[:400])
        return 1
    print("summon1:", json.dumps(U.mouse_click("document.querySelectorAll('.ec-card-summon-btn')[0]"),
                                 ensure_ascii=False))
    time.sleep(4.0)
    print("after:", json.dumps(U.js(r"""(()=>({
      txt:(document.body.innerText||'').replace(/\s+/g,' ').slice(0,700),
      convoTitles:Array.from(document.querySelectorAll('.conversation-item')).map(e=>(e.innerText||'').replace(/\s+/g,' ').trim().slice(0,42)),
      ecCards:document.querySelectorAll('.ec-expert-card').length,
      hasInput:!!document.querySelector('[contenteditable=true]')
    }))()"""), ensure_ascii=False, indent=1)[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
