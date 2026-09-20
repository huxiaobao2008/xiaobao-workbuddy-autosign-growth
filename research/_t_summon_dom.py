"""诊断：召唤专家团后，输入框里到底挂了什么？
对比专家（kind=expert）与专家团（kind=team）召唤后 composer 的 DOM 差异。
"""
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
  const ed = document.querySelector('[contenteditable=true]');
  const box = ed ? (ed.closest('.wb-home-route__input-box, .cr-input-box') || ed.parentElement) : null;
  const chips = [...document.querySelectorAll('.phrase-content-wrapper')].map(T);
  return {
    hasEd: !!ed,
    text: ed ? T(ed).slice(0, 80) : null,
    chips: chips,
    // 输入框容器里所有带 chip/mention/expert/team/tag 关键字的元素
    boxKids: box ? [...box.querySelectorAll('*')]
      .filter(e => /chip|mention|expert|team|tag/i.test((e.className || '').toString()))
      .map(e => (e.className || '').toString().slice(0, 70)).slice(0, 14) : null,
    boxHTML: box ? box.innerHTML.replace(/\s+/g, ' ').slice(0, 900) : null
  };
})()
"""


def run(kind, idx):
    print('\n########## kind=%s idx=%d ##########' % (kind, idx), flush=True)
    U.js('(async()=>{ await openNewTask(); return 1; })()', timeout=60)
    time.sleep(1.5)
    try:
        print('clear:', json.dumps(U.clear_input(), ensure_ascii=False), flush=True)
    except Exception as e:
        print('clear err', str(e)[:100], flush=True)
    steps, gaps = UT._expert_steps(kind, None, idx)
    for i, s in enumerate(steps):
        try:
            r = U.js(s, timeout=90)
        except Exception as e:
            r = {'EXC': '%s: %s' % (type(e).__name__, str(e)[:90])}
        print('step%d %s' % (i, json.dumps(r, ensure_ascii=False)[:220]), flush=True)
        if i < len(steps) - 1:
            time.sleep(gaps[min(i, len(gaps) - 1)])
    d = U.js(DUMP, timeout=60)
    print('COMPOSER:', json.dumps(d, ensure_ascii=False, indent=1)[:1800], flush=True)
    return d


d1 = run('expert', 0)
d2 = run('team', 0)
print('\n=== 差异 ===')
print('expert chips:', json.dumps(d1.get('chips'), ensure_ascii=False))
print('team   chips:', json.dumps(d2.get('chips'), ensure_ascii=False))
