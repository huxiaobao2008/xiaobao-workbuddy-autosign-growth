"""dump 灵感卡片详情弹窗（dc-detail-modal）的结构与可点元素。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_driver as U  # noqa: E402
import ui_tasks as UT  # noqa: E402

MODAL = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const m = document.querySelector('.dc-detail-modal-body')
         || document.querySelector('[class*=dc-detail-modal]');
  if (!m) return { err: '没有详情弹窗' };
  const clicks = [...m.querySelectorAll('button,[role=button],[class*=btn],[class*=action]')]
    .filter(vis).map(e => ({ tag: e.tagName, cls: (e.className || '').toString().slice(0, 56),
                             t: T(e).slice(0, 24) })).slice(0, 20);
  return {
    modalCls: (m.className || '').toString().slice(0, 80),
    modalText: T(m).slice(0, 300),
    clickables: clicks,
    html: m.outerHTML.replace(/\s+/g, ' ').slice(0, 2200)
  };
})()
"""

U.js('(async()=>{ await openNewTask(); return 1; })()', timeout=60)
time.sleep(2.5)
print('card:', json.dumps(U.js(UT._pb_card_step(0), timeout=90), ensure_ascii=False), flush=True)
time.sleep(5)
d = U.js(MODAL, timeout=60)
print('\n=== 详情弹窗 ===', flush=True)
print(json.dumps({k: d.get(k) for k in ('modalCls', 'modalText', 'clickables')},
                 ensure_ascii=False, indent=1)[:1600], flush=True)
print('\n--- html ---', flush=True)
print((d.get('html') or '')[:2200], flush=True)
