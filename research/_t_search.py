"""诊断搜索：搜索框当前值 / 结果卡片名 / 搜索是否真的生效。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_driver as U  # noqa: E402
import ui_tasks as UT  # noqa: E402

SNAP = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const si = document.querySelector('.ec-search-wrapper input');
  return {
    searchVal: si ? si.value : null,
    searchCls: si ? (si.className || '').toString().slice(0, 60) : null,
    cards: [...document.querySelectorAll('.ec-expert-card')].map(e => T(e).slice(0, 30)).slice(0, 12),
    nCards: document.querySelectorAll('.ec-expert-card').length,
    count: (document.querySelector('.ec-expert-count') || {}).innerText || null,
    activeListTab: [...document.querySelectorAll('.ec-list-tab.is-active')].map(T),
    gridItems: document.querySelectorAll('.ec-expert-grid-item').length,
    hits: [...document.querySelectorAll('button,div,span,a')]
      .filter(e => { const t = T(e); return t && /授权|连接器|允许|启用|开通/.test(t) && t.length < 30
                            && (() => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4; })(); })
      .map(e => ({ cls: (e.className || '').toString().slice(0, 50), t: T(e).slice(0, 40) })).slice(0, 10)
  };
})()
"""


def snap(tag):
    d = U.js(SNAP, timeout=60)
    print('\n== %s ==' % tag, flush=True)
    print(json.dumps(d, ensure_ascii=False, indent=1)[:1400], flush=True)
    return d


U.js('(async()=>{ await openNewTask(); return 1; })()', timeout=60)
time.sleep(1.5)
U.js(UT.EXPERT_ENTER_STEP, timeout=90)
time.sleep(7)
snap('进入专家中心（默认 tab）')

print('\n--- 填搜索框 轻量云 ---', flush=True)
r = U.js("""(async () => {
  const si = document.querySelector('.ec-search-wrapper input');
  if (!si) return { err: 'no input' };
  realClick(si);
  await sleep(300);
  setReactInput(si, '');
  await sleep(800);
  setReactInput(si, '轻量云');
  await sleep(3000);
  return { ok: true, val: si.value };
})()""", timeout=90)
print(json.dumps(r, ensure_ascii=False), flush=True)
time.sleep(4)
snap('搜索后')
