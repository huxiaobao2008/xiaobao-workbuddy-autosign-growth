#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""界面勘察：依次点开左侧一级入口，dump 每个视图的关键元素。一次 JS 调用跑完。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import account_switch as AS   # noqa: E402
import ui_driver as U         # noqa: E402

JS = r"""
(async () => {
  const out = { visits: [] };
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 20 && r.height > 12; };
  const label = el => (el.innerText || el.getAttribute('aria-label') || '')
      .replace(/\s+/g, ' ').trim();

  function clickByText(t) {
    const cands = Array.from(document.querySelectorAll('button, [role=button], a, div, span, li'))
      .filter(el => vis(el) && label(el) === t);
    if (!cands.length) return null;
    // 取最深的（文本节点所在的那个）
    cands.sort((a, b) => b.querySelectorAll('*').length - a.querySelectorAll('*').length);
    const el = cands[cands.length - 1];
    const r = el.getBoundingClientRect();
    const opt = { bubbles: true, cancelable: true, composed: true,
                  clientX: r.left + r.width / 2, clientY: r.top + r.height / 2,
                  view: window, button: 0 };
    ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(ty =>
      el.dispatchEvent(ty.startsWith('pointer') ? new PointerEvent(ty, opt) : new MouseEvent(ty, opt)));
    return { txt: label(el), cls: el.className.toString().slice(0, 70) };
  }

  function snapshot(name) {
    const labs = [];
    document.querySelectorAll('button, [role=button], a, [class*=tab], [class*=item], [class*=card]')
      .forEach(el => { if (vis(el)) { const t = label(el); if (t && t.length <= 30) labs.push(t); } });
    const uniq = Array.from(new Set(labs));
    const cls = Array.from(new Set(Array.from(document.querySelectorAll('*')).map(e => e.className && e.className.toString()).filter(Boolean)
      .flatMap(c => c.split(/\s+/)).filter(c => /expert|skill|library|playbook|automation|buddy|appear|canvas|design|team|store|install/i.test(c))));
    out.visits.push({ name: name, n: uniq.length, labels: uniq.slice(0, 90), classes: cls.slice(0, 60) });
  }

  for (const entry of ['资料库', '灵感', '定时任务', '发现应用', '专家·技能·连接器']) {
    const r = clickByText(entry);
    await sleep(2200);
    snapshot(entry + (r ? ' [clicked ' + r.cls + ']' : ' [NOT FOUND]'));
    // 回首页，避免状态叠加
    clickByText('新建任务');
    await sleep(1500);
  }
  return out;
})()
"""


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "account_f"
    sw = AS.switch_to(key, reload=False)
    print("switch ok=%s menu=%s" % (sw.get("ok"), (sw.get("after") or {}).get("menu")))
    if not sw.get("ok"):
        return 1
    try:
        r = U.js(JS, timeout=280)
        print(json.dumps(r, ensure_ascii=False, indent=2)[:14000])
    finally:
        back = AS.switch_to("account_a", reload=False)
        print("back ok=%s menu=%s" % (back.get("ok"), (back.get("after") or {}).get("menu")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
