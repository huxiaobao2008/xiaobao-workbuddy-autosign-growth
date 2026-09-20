# -*- coding: utf-8 -*-
"""灵感案例：卡片 → 做同款 → 输入框。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_driver as U  # noqa: E402

S_HOME = """(async () => { await openNewTask(); await sleep(1500);
  return { home: !!document.querySelector('.wb-home-composer__chips') }; })()"""

S_CLEAR = """(async () => {
  const btn = Array.from(document.querySelectorAll('button, [class*=close], [class*=clear]'))
    .filter(b => /关闭|取消|返回/.test((b.innerText||'').trim())).filter(b => {const r=b.getBoundingClientRect(); return r.width>8&&r.height>8;})[0];
  if (btn) { realClick(btn); await sleep(1500); }
  return { dismissed: !!btn };
})()"""

S_IDEAS = """(() => {
  const T = el => (el.innerText || '').replace(/\\s+/g, ' ').trim();
  const sub = Array.from(document.querySelectorAll('.conversation-list-tab-button-sub'))
    .find(e => T(e).indexOf('灵感') !== -1);
  if (sub) realClick(sub);
  return { sideClicked: sub ? T(sub) : null };
})()"""

S_CARD = """(() => {
  const T = el => (el.innerText || '').replace(/\\s+/g, ' ').trim();
  const cards = Array.from(document.querySelectorAll('.wb-related-playbooks__card'));
  if (!cards.length) return { err: '没有灵感卡片' };
  const c = cards[%d];
  realClick(c);
  return { clicked: T(c).slice(0, 40) };
})()"""

S_SAME = """(() => {
  const T = el => (el.innerText || '').replace(/\\s+/g, ' ').trim();
  const vis = b => { const r = b.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const all = Array.from(document.querySelectorAll('button')).filter(vis);
  const same = all.find(b => T(b) === '做同款') || all.find(b => /做同款/.test(T(b)));
  if (!same) return { err: '没有做同款按钮', buttons: all.map(b => T(b)).filter(Boolean).slice(0, 30) };
  realClick(same);
  return { clicked: T(same) };
})()"""

S_STATE = """(() => {
  const T = el => (el.innerText || '').replace(/\\s+/g, ' ').trim();
  const ed = document.querySelector('[contenteditable=true]');
  return {
    edText: ed ? (ed.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 220) : null,
    chips: Array.from(document.querySelectorAll('.phrase-content-wrapper')).map(T),
    hasSend: !!document.querySelector('button.cr-send-button'),
    view: !!document.querySelector('.cr-message-list-viewport'),
    scripted: !!document.querySelector('[class*=playbook], [class*=inspiration]')
  };
})()"""


def step(js, t=40, name=""):
    try:
        return U.js(js, timeout=t)
    except Exception as e:
        return {"ERR": "%s: %s" % (type(e).__name__, str(e)[:70])}


if __name__ == "__main__":
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    print("1)", json.dumps(step(S_HOME, 60), ensure_ascii=False))
    print("2)", json.dumps(step(S_IDEAS, 30), ensure_ascii=False))
    time.sleep(5)
    print("3)", json.dumps(step(S_CARD % idx, 30), ensure_ascii=False))
    time.sleep(6)
    print("4)", json.dumps(step(S_SAME, 30), ensure_ascii=False))
    time.sleep(6)
    print("5)", json.dumps(step(S_STATE, 40), ensure_ascii=False, indent=2))
