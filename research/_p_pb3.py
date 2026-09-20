#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""灵感案例：回首页 → 找「最佳实践案例」卡片 → 点第一个 → 观察。"""
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

FIND = r"""(()=>{
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const rect = e => { const r = e.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  // 找「最佳实践案例」标题
  const title = Array.from(document.querySelectorAll('*')).filter(vis)
    .find(e => /最佳实践案例|试试最佳实践/.test(e.innerText||'') && (e.innerText||'').length < 25);
  const titleRect = title ? rect(title) : null;
  // 卡片：标题下方一行、尺寸相近的块
  let cards = [];
  if (titleRect) {
    cards = Array.from(document.querySelectorAll('div,[class*=card]')).filter(vis)
      .filter(e => { const r = e.getBoundingClientRect();
        return r.top > titleRect[1] + 10 && r.top < titleRect[1] + 220
            && r.height > 70 && r.height < 260 && r.width > 120 && r.width < 340; })
      .map(e => ({ cls: String(e.className).slice(0, 80),
                   t: (e.innerText||'').replace(/\s+/g,' ').trim().slice(0, 40),
                   kids: e.querySelectorAll('*').length, r: rect(e) }));
  }
  return { titleCls: title ? String(title.className).slice(0, 80) : null, titleRect,
           cards: cards.slice(0, 12) };
})()"""


def main():
    T.dismiss_overlays()
    print("home:", json.dumps(U.mouse_click(HOME), ensure_ascii=False))
    time.sleep(3.0)
    print("find:", json.dumps(U.js(FIND), ensure_ascii=False, indent=1)[:2500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
