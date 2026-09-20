"""验证：进入专家中心后改用 Python 侧等待，列表能否正常渲染。
思路：JS 调用只做「点击」，等待交给 Python 的 time.sleep（不受页面卡顿影响）。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_driver as U  # noqa: E402

T = """const T = el => (el.innerText || '').replace(/\\s+/g, ' ').trim();"""

CLICK = """
const click = (el) => { const r = el.getBoundingClientRect();
  for (const t of ['pointerdown','mousedown','pointerup','mouseup','click']) {
    el.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t,
      { bubbles: true, cancelable: true, view: window,
        clientX: r.x + r.width/2, clientY: r.y + r.height/2, button: 0, buttons: 1 }));
  } };
"""


def snap(tag):
    r = U.js("""(() => {
      const g = document.querySelector('.ec-expert-grid');
      const cnt = document.querySelector('.ec-expert-count');
      return { items: document.querySelectorAll('.ec-expert-grid-item').length,
               cards: document.querySelectorAll('.ec-expert-card').length,
               summon: document.querySelectorAll('.ec-card-summon-btn').length,
               count: cnt ? cnt.innerText : null,
               activeTabs: [...document.querySelectorAll('.ec-list-tab.is-active')].map(e => e.innerText.trim()),
               gridLen: g ? g.innerHTML.length : -1 };
    })()""", timeout=30)
    print(tag, json.dumps(r, ensure_ascii=False), flush=True)
    return r


print('--- openNewTask ---', flush=True)
U.js('(async()=>{ await openNewTask(); return 1; })()', timeout=60)
time.sleep(2)

print('--- click sidebar 专家 entry ---', flush=True)
U.js("""(async () => { %s %s
  if (document.querySelector('.ec-list-tab')) return { already: true };
  const e = [...document.querySelectorAll('button.conversation-list-tab-button')]
    .find(b => T(b).indexOf('专家') !== -1);
  if (!e) return { err: 'no entry' };
  click(e); return { clicked: true };
})()""" % (T, CLICK), timeout=60)

for i in range(1, 13):
    time.sleep(10)
    try:
        r = snap('t+%ds' % (i * 10))
    except Exception as e:
        print('t+%ds READ FAIL %s' % (i * 10, type(e).__name__), flush=True)
        continue
    if r.get('cards'):
        print('*** cards appeared at t+%ds ***' % (i * 10), flush=True)
        break
