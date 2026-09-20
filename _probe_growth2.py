# -*- coding: utf-8 -*-
"""探测成长计划页：先找 Buddy加油站 卡片与盲盒/派猫猫旅行 入口。"""
import json
import ui_driver as U

js = r"""
(() => {
  const T = el => (el.innerText||'').replace(/\s+/g,' ').trim();
  const vis = el => { const r = el.getBoundingClientRect(); return r.width>8 && r.height>8; };
  const re = /盲盒|派|旅行|猫猫|加油站|成长|今日可领|去领取|任务/;
  const hits = [];
  document.querySelectorAll('*').forEach(e => {
    if (!vis(e)) return;
    const t = T(e);
    if (re.test(t) && e.children.length <= 4) {
      let c = e;
      while (c && c !== document.body) {
        if (c.tagName === 'BUTTON' || c.tagName === 'A' || c.getAttribute('role') === 'button') break;
        c = c.parentElement;
      }
      hits.push({
        text: t.slice(0,70),
        tag: e.tagName,
        cls: String(e.className).slice(0,55),
        click: (c && c!==e) ? (c.tagName + ' ' + String(c.className).slice(0,45)) : (e.tagName==='BUTTON'||e.tagName==='A' ? 'self' : null)
      });
    }
  });
  return { count: hits.length, hits: hits.slice(0,70) };
})()
"""
print(json.dumps(U.js(js, timeout=50), ensure_ascii=False, indent=2, default=str))
