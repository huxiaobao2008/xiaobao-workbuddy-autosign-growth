# -*- coding: utf-8 -*-
"""灵感案例：点侧边栏「灵感」→ 点一张灵感卡片 → 看输入框被填了什么。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_driver as U  # noqa: E402

S1 = """(async () => { await openNewTask(); await sleep(1500);
  return { home: !!document.querySelector('.wb-home-composer__chips') }; })()"""

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

S_STATE = """(() => {
  const T = el => (el.innerText || '').replace(/\\s+/g, ' ').trim();
  const ed = document.querySelector('[contenteditable=true]');
  return {
    edText: ed ? (ed.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 260) : null,
    chips: Array.from(document.querySelectorAll('.phrase-content-wrapper')).map(T),
    hasSend: !!document.querySelector('button.cr-send-button'),
    view: !!document.querySelector('.cr-message-list-viewport'),
    body: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-260)
  };
})()"""


def step(js, t=40):
    try:
        return U.js(js, timeout=t)
    except Exception as e:
        return {"ERR": "%s: %s" % (type(e).__name__, str(e)[:70])}


if __name__ == "__main__":
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    print("1)", json.dumps(step(S1, 60), ensure_ascii=False))
    print("2)", json.dumps(step(S_IDEAS, 30), ensure_ascii=False))
    time.sleep(5)
    print("3)", json.dumps(step(S_CARD % idx, 30), ensure_ascii=False))
    time.sleep(6)
    print("4)", json.dumps(step(S_STATE, 40), ensure_ascii=False, indent=2))
