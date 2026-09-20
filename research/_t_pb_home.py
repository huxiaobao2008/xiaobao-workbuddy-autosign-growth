"""诊断 playbook：首页是否自带「灵感」卡片（可绕开侧边栏→导航那条路）。
顺便清掉本账号的残留会话。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_driver as U  # noqa: E402

HOME_DUMP = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const cards = [...document.querySelectorAll('.wb-related-playbooks__card')].filter(vis);
  const slot = document.querySelector('.wb-home-page__related-playbooks-slot');
  return {
    nCards: cards.length,
    cardNames: cards.map(c => T(c).slice(0, 30)).slice(0, 6),
    slotExists: !!slot,
    slotText: slot ? T(slot).slice(0, 160) : null,
    sameBtns: [...document.querySelectorAll('button')].filter(vis)
      .map(b => T(b)).filter(t => /做同款|同款|用这个/.test(t)).slice(0, 6),
    editable: !!document.querySelector('[contenteditable=true]'),
    titles: (function () { try { return taskTitles(); } catch (e) { return null; } })()
  };
})()
"""

print('=== 先清残留会话 ===', flush=True)
ts = U.task_titles()
print('before:', json.dumps(ts, ensure_ascii=False), flush=True)
if ts:
    U.js('(async()=>{ await openNewTask(); return 1; })()', timeout=60)
    time.sleep(2)
    for t in ts:
        key = t.split('简单介绍')[0][:16]
        r = U.delete_conversation(key)
        print('del', key, '->', json.dumps({k: r.get(k) for k in ('ok', 'gone', 'err')}, ensure_ascii=False), flush=True)
        time.sleep(1.5)
print('after:', json.dumps(U.task_titles(), ensure_ascii=False), flush=True)

print('\n=== 首页灵感卡片结构 ===', flush=True)
U.js('(async()=>{ await openNewTask(); return 1; })()', timeout=60)
time.sleep(2.5)
d = U.js(HOME_DUMP, timeout=60)
print(json.dumps(d, ensure_ascii=False, indent=1)[:1600], flush=True)
