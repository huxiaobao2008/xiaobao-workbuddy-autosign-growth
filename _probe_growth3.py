# -*- coding: utf-8 -*-
"""回首页 -> 找 Buddy加油站/成长 入口 -> 打开成长计划页 -> 探盲盒/派猫猫旅行。"""
import json
import time
import ui_driver as U

# 1) 回首页
U.js("(async () => { await openNewTask(); return true; })()", timeout=60)
time.sleep(1.5)

# 2) 扫描首页里与成长计划相关的可见元素
scan = r"""
(() => {
  const T = el => (el.innerText||'').replace(/\s+/g,' ').trim();
  const vis = el => { const r=el.getBoundingClientRect(); return r.width>8 && r.height>8; };
  const out = [];
  document.querySelectorAll('*').forEach(e => {
    if (!vis(e)) return;
    const t = T(e);
    if (/加油站|成长计划|成长中心|猫猫|盲盒|旅行|派/.test(t) && e.children.length <= 4) {
      let c = e;
      while (c && c !== document.body) {
        if (c.tagName === 'BUTTON' || c.tagName === 'A' || c.getAttribute('role') === 'button') break;
        c = c.parentElement;
      }
      out.push({ text: t.slice(0,80), tag: e.tagName, cls: String(e.className).slice(0,55),
                 click: (c && c!==e) ? (c.tagName + ' ' + String(c.className).slice(0,40)) : (e.tagName==='BUTTON'||e.tagName==='A'?'self':null) });
    }
  });
  return out.slice(0,40);
})()
"""
hits = U.js(scan, timeout=40)
print("HOME SCAN:", json.dumps(hits, ensure_ascii=False, indent=2, default=str))
