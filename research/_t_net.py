"""诊断：专家中心列表为空 —— 是接口没返回，还是前端渲染失败？
做法：先在页面里挂 fetch/XHR 拦截器（只记录 url/status/长度），
再在应用内导航到专家中心（不 reload，拦截器不会丢），最后 dump 记录。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_driver as U  # noqa: E402

PATCH = r"""
(() => {
  if (window.__netPatched) return { already: true };
  window.__netPatched = true;
  window.__net = [];
  const rec = (o) => { try { window.__net.push(o); if (window.__net.length > 80) window.__net.shift(); } catch (e) {} };
  const of = window.fetch;
  window.fetch = async function (...a) {
    const url = (typeof a[0] === 'string') ? a[0] : (a[0] && a[0].url) || '';
    try {
      const r = await of.apply(this, a);
      let len = null;
      try { len = (await r.clone().text()).length; } catch (e) {}
      rec({ k: 'fetch', url: url.slice(-90), status: r.status, len: len });
      return r;
    } catch (e) {
      rec({ k: 'fetch', url: url.slice(-90), err: String(e).slice(0, 60) });
      throw e;
    }
  };
  const oo = XMLHttpRequest.prototype.open;
  const os = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u, ...rest) { this.__u = u; return oo.call(this, m, u, ...rest); };
  XMLHttpRequest.prototype.send = function (...a) {
    this.addEventListener('loadend', () => {
      rec({ k: 'xhr', url: String(this.__u).slice(-90), status: this.status,
            len: (this.responseText || '').length });
    });
    return os.apply(this, a);
  };
  return { patched: true };
})()
"""

CLICK_SIDE = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  if (document.querySelector('.ec-list-tab')) return { already: true };
  const e = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
    .find(b => T(b).indexOf('专家') !== -1);
  if (!e) return { err: 'no entry' };
  const r = e.getBoundingClientRect();
  for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
    e.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t,
      { bubbles: true, cancelable: true, view: window,
        clientX: r.x + r.width / 2, clientY: r.y + r.height / 2, button: 0, buttons: 1 }));
  }
  return { clicked: true };
})()
"""


def dump(tag):
    r = U.js(r"""(() => ({
      net: (window.__net || []).slice(-25),
      items: document.querySelectorAll('.ec-expert-grid-item').length,
      cards: document.querySelectorAll('.ec-expert-card').length,
      featCards: document.querySelectorAll('.ec-featured-scene-card').length,
      featNames: [...document.querySelectorAll('.ec-featured-scene-name')].map(e => e.innerText.trim()).slice(0, 14),
      cnt: (document.querySelector('.ec-expert-count') || {}).innerText || null
    }))()""", timeout=30)
    print('== %s ==' % tag, flush=True)
    print(json.dumps(r, ensure_ascii=False, indent=1)[:2600], flush=True)
    return r


print('patch:', json.dumps(U.js(PATCH, timeout=30), ensure_ascii=False), flush=True)
U.js('(async()=>{ await openNewTask(); return 1; })()', timeout=60)
time.sleep(2)
print('click:', json.dumps(U.js(CLICK_SIDE, timeout=60), ensure_ascii=False), flush=True)
time.sleep(45)
dump('t+45s')
time.sleep(25)
dump('t+70s')
