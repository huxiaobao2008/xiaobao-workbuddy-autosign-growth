"""诊断 Expert_team_use_3 为何不计数：对比「召唤专家」与「召唤专家团」时
客户端发出的建会话请求，找出服务端用来区分两者的字段。

做法：在页面里挂 fetch/XHR 拦截器，记录所有 POST 的 url + body（截断），
分别跑一次专家 / 一次专家团的「召唤 + 发一句话」，然后对比。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_driver as U  # noqa: E402
import ui_tasks as UT  # noqa: E402

PATCH = r"""
(() => {
  if (window.__net2) return { already: true };
  window.__net2 = [];
  const rec = (o) => { try { window.__net2.push(o); if (window.__net2.length > 120) window.__net2.shift(); } catch (e) {} };
  const of = window.fetch;
  window.fetch = async function (...a) {
    const url = (typeof a[0] === 'string') ? a[0] : (a[0] && a[0].url) || '';
    const opt = (typeof a[0] === 'object' && a[0]) || a[1] || {};
    const m = (opt.method || 'GET').toUpperCase();
    let body = opt.body;
    try { if (body && typeof body !== 'string') body = JSON.stringify(body); } catch (e) {}
    const interesting = /conversation|chat|expert|session|assistant/i.test(url);
    if (m !== 'GET' || interesting) {
      rec({ k: 'fetch', m: m, url: url.replace(/^https?:\/\/[^/]+/, '').slice(0, 110),
            body: body ? String(body).slice(0, 700) : null });
    }
    return of.apply(this, a);
  };
  const oo = XMLHttpRequest.prototype.open;
  const os = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u, ...r) { this.__u = u; this.__m = m; return oo.call(this, m, u, ...r); };
  XMLHttpRequest.prototype.send = function (b, ...r) {
    try {
      const u = String(this.__u || '');
      if ((this.__m || 'GET').toUpperCase() !== 'GET' || /conversation|chat|expert/i.test(u)) {
        rec({ k: 'xhr', m: this.__m, url: u.replace(/^https?:\/\/[^/]+/, '').slice(0, 110),
              body: b ? String(b).slice(0, 700) : null });
      }
    } catch (e) {}
    return os.call(this, b, ...r);
  };
  return { patched: true };
})()
"""


def dump(tag):
    r = U.js("(() => (window.__net2 || []).slice(-14))()", timeout=40)
    print('\n---- %s: 最近 %d 条 ----' % (tag, len(r or [])), flush=True)
    for x in (r or []):
        print('  [%s] %s' % (x.get('m'), x.get('url')), flush=True)
        if x.get('body'):
            print('       body: %s' % x['body'][:420], flush=True)


def clear():
    U.js("(() => { window.__net2 = []; return 1; })()", timeout=30)


def one(kind, idx, tag):
    print('\n========== %s (kind=%s idx=%d) ==========' % (tag, kind, idx), flush=True)
    clear()
    U.js('(async()=>{ await openNewTask(); return 1; })()', timeout=60)
    time.sleep(1.2)
    U.clear_input()
    steps, gaps = UT._expert_steps(kind, None, idx)
    for i, s in enumerate(steps):
        try:
            U.js(s, timeout=120)
        except Exception as e:
            print('  step%d EXC %s' % (i, str(e)[:80]), flush=True)
        if i < len(steps) - 1:
            time.sleep(gaps[min(i, len(gaps) - 1)])
    U.type_text('用一句话回答。')
    time.sleep(1.0)
    U.js('(async () => { const s = send(); return s; })()', timeout=60)
    time.sleep(12)
    dump(tag)


print('patch:', json.dumps(U.js(PATCH, timeout=40), ensure_ascii=False), flush=True)
one('expert', 0, 'A-专家')
one('team', 0, 'B-专家团')
