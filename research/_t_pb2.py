"""逐段诊断 playbook：首页 → 点卡片 → 有什么 → 点做同款 → 输入框状态。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_driver as U  # noqa: E402
import ui_tasks as UT  # noqa: E402

DUMP = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const ed = document.querySelector('[contenteditable=true]');
  return {
    url: location.href.slice(-46),
    edText: ed ? T(ed).slice(0, 70) : null,
    nCards: [...document.querySelectorAll('.wb-related-playbooks__card')].filter(vis).length,
    btnLabels: [...document.querySelectorAll('button')].filter(vis).map(T)
      .filter(t => t && t.length < 14).slice(0, 24),
    overlays: [...document.querySelectorAll('[class*=overlay],[class*=modal],[class*=dialog]')]
      .filter(vis).map(e => (e.className || '').toString().slice(0, 56)).slice(0, 8),
    detailText: (() => { const d = document.querySelector('.detail-panel, [class*=playbook-detail]');
                         return d ? T(d).slice(0, 140) : null; })(),
    bodyHead: T(document.body).slice(0, 180)
  };
})()
"""


def dump(tag):
    d = U.js(DUMP, timeout=60)
    print('\n===== %s =====' % tag, flush=True)
    print(json.dumps(d, ensure_ascii=False, indent=1)[:1500], flush=True)
    return d


print('--- 回首页 ---', flush=True)
U.js('(async()=>{ await openNewTask(); return 1; })()', timeout=60)
time.sleep(2.5)
dump('首页')

print('\n--- 点第 1 张卡片 ---', flush=True)
print(json.dumps(U.js(UT._pb_card_step(0), timeout=90), ensure_ascii=False), flush=True)
time.sleep(5)
dump('点卡片后')

print('\n--- 点「做同款」---', flush=True)
print(json.dumps(U.js(UT.PB_SAME, timeout=90), ensure_ascii=False), flush=True)
time.sleep(5)
dump('做同款后')

print('\n--- 点「替换」 ---', flush=True)
print(json.dumps(U.js(UT.PB_REPLACE, timeout=90), ensure_ascii=False), flush=True)
time.sleep(3)
dump('替换后')
