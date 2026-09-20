# -*- coding: utf-8 -*-
"""只读扫描当前页面里成长计划相关入口：加油站/成长/盲盒/派送/赠送/任务。"""
import json
import ui_driver as U

js = r"""
(() => {
  const T = el => (el.innerText||'').replace(/\s+/g,' ').trim();
  const vis = el => { const r=el.getBoundingClientRect(); return r.width>8 && r.height>8; };
  // 1) 全页可见的、含关键词的小节点
  const hits = Array.from(document.querySelectorAll('*'))
    .filter(e => vis(e) && e.children.length<=2)
    .map(e => ({ t:T(e), cls:String(e.className).slice(0,70), tag:e.tagName }))
    .filter(x => /加油站|成长|盲盒|派送|赠送|送礼|分享|礼物|任务|积分|领取/.test(x.t));
  // 2) 若已有成长计划面板，抓它的任务卡片（带可能的 data-code）
  const panel = document.querySelector('[class*=growth], [class*=Growth], [class*=task-center], [class*=TaskCenter]');
  let cards = [];
  if (panel) {
    cards = Array.from(panel.querySelectorAll('[class*=task], [class*=card], [class*=item]'))
      .filter(vis)
      .map(c => ({ t:T(c).slice(0,40), code:c.getAttribute('data-code')||c.getAttribute('data-task-code')||null }));
  }
  return { hits: hits.slice(0,50), panelFound: !!panel, cards: cards.slice(0,60) };
})()
"""
print(json.dumps(U.js(js, timeout=40), ensure_ascii=False, indent=2, default=str))
