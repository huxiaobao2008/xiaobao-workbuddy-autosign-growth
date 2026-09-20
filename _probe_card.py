# -*- coding: utf-8 -*-
"""探测 Buddy加油站 浮卡 DOM，找到成长计划页入口。"""
import json
import ui_driver as U

js = r"""
(() => {
  const T = el => (el.innerText||'').replace(/\s+/g,' ').trim();
  const vis = el => { const r=el.getBoundingClientRect(); return r.width>8 && r.height>8; };
  const LEAF = el => el.querySelectorAll(':scope > *').length <= 6;
  // 含 Buddy加油站 / 今日可领 / 成长 的容器
  const cards = Array.from(document.querySelectorAll('div,section,aside'))
    .filter(e => vis(e) && LEAF(e) && /Buddy加油站|加油站|今日可领|成长计划/.test(T(e))))
    .map(e => {
      const btns = Array.from(e.querySelectorAll('button,a,[role=button]'))
        .filter(vis)
        .map(b => ({ t:T(b), cls:String(b.className).slice(0,60), tag:b.tagName }));
      return { t:T(e).slice(0,120), cls:String(e.className).slice(0,80), btns };
    });
  // 全页按钮中含 盲盒/派送/今日可领/去领取/成长
  const btns = Array.from(document.querySelectorAll('button,a,[role=button]'))
    .filter(vis)
    .map(b => ({ t:T(b), cls:String(b.className).slice(0,60), tag:b.tagName }))
    .filter(x => /盲盒|派送|赠送|今日可领|成长|加油站|去领取/.test(x.t));
  return { cards: cards.slice(0,20), btns: btns.slice(0,40) };
})()
"""
print(json.dumps(U.js(js, timeout=40), ensure_ascii=False, indent=2, default=str))
