"""诊断 Expert_lighthouse：召唤「腾讯轻量云」专家后，输入框上方出现的「授权连接器」是什么。
任务描述：召唤专家 → **在对话框上方授权连接器** → 对话一次。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_driver as U  # noqa: E402
import ui_tasks as UT  # noqa: E402

ABOVE = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const ed = document.querySelector('[contenteditable=true]');
  if (!ed) return { err: 'no editor' };
  let host = ed.closest('.cr-input-container, .cr-input-box, .wb-home-route__input-box, .cr-input-container-wrapper');
  const chain = [];
  let cur = ed.parentElement;
  for (let i = 0; i < 8 && cur; i++) {
    chain.push({ i: i, cls: (cur.className || '').toString().slice(0, 70),
                 txt: T(cur).slice(0, 90) });
    cur = cur.parentElement;
  }
  // 找「授权 / 连接器 / 允许 / 使用」相关按钮与提示
  const hits = [...document.querySelectorAll('button,div,span,a')]
    .filter(e => { const t = T(e); return t && /授权|连接器|允许|启用|开通|去授权|一键授权/.test(t)
                          && t.length < 40; })
    .map(e => ({ tag: e.tagName, cls: (e.className || '').toString().slice(0, 60),
                 t: T(e).slice(0, 50),
                 vis: (() => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4; })() }))
    .slice(0, 20);
  const boxHTML = host ? host.outerHTML.replace(/\s+/g, ' ').slice(0, 1600) : null;
  return { chain: chain, hits: hits, boxHTML: boxHTML,
           editableText: T(ed).slice(0, 60),
           chips: [...document.querySelectorAll('.cr-chip-label')].map(T) };
})()
"""

print('=== 召唤「腾讯轻量云」专家（account_e）===', flush=True)
U.js('(async()=>{ await openNewTask(); return 1; })()', timeout=60)
time.sleep(1.5)
U.clear_input()
steps, gaps = UT._expert_steps('search', '轻量云', 0)
for i, s in enumerate(steps):
    try:
        r = U.js(s, timeout=120)
    except Exception as e:
        r = {'EXC': str(e)[:90]}
    print('step%d %s' % (i, json.dumps(r, ensure_ascii=False)[:260]), flush=True)
    if i < len(steps) - 1:
        time.sleep(gaps[min(i, len(gaps) - 1)])
time.sleep(3)
d = U.js(ABOVE, timeout=60)
print('\n=== 输入框周围的「授权/连接器」===', flush=True)
print(json.dumps({k: d.get(k) for k in ('editableText', 'chips', 'hits', 'chain')},
                 ensure_ascii=False, indent=1)[:2000], flush=True)
print('\n--- boxHTML ---', flush=True)
print((d.get('boxHTML') or '')[:1500], flush=True)
