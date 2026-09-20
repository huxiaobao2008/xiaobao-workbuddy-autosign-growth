# -*- coding: utf-8 -*-
"""灵感页探测：点击与读取分两次 JS 调用（点击会触发导航，同一次调用会被中断）。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_driver as U  # noqa: E402

S1 = """(async () => { await closeOverlays(3); await openNewTask(); await sleep(1500);
  return { home: !!document.querySelector('.wb-home-composer__chips') }; })()"""

S2 = """(() => {
  const T = el => (el.innerText || '').replace(/\\s+/g, ' ').trim();
  const sub = Array.from(document.querySelectorAll('.conversation-list-tab-button-sub'))
    .find(e => T(e).indexOf('灵感') !== -1);
  if (!sub) return { err: '没有灵感 sub 入口',
                     subs: Array.from(document.querySelectorAll('.conversation-list-tab-button-sub')).map(T) };
  realClick(sub);
  return { clicked: T(sub), cls: sub.className.toString() };
})()"""

S3 = """(() => {
  const T = el => (el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 80);
  return {
    url: location.href.slice(-80),
    cls: Array.from(new Set(Array.from(document.querySelectorAll('[class*=inspiration], [class*=playbook], [class*=idea], [class*=explore], [class*=case]'))
      .map(e => e.className.toString().split(' ')[0]))).slice(0, 60),
    cards: Array.from(document.querySelectorAll('.wb-related-playbooks__card, [class*=playbook-card], [class*=inspiration-card], article'))
      .map(e => ({ tag: e.tagName.toLowerCase(), cls: e.className.toString().slice(0, 60), t: T(e).slice(0, 40) })).slice(0, 20),
    body: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 900)
  };
})()"""


def step(js, t=40):
    try:
        return U.js(js, timeout=t)
    except Exception as e:
        return {"ERR": "%s: %s" % (type(e).__name__, str(e)[:80])}


if __name__ == "__main__":
    print("1)", json.dumps(step(S1, 60), ensure_ascii=False))
    print("2)", json.dumps(step(S2, 30), ensure_ascii=False))
    time.sleep(6)
    try:
        print("3)", json.dumps(step(S3, 40), ensure_ascii=False, indent=2))
    except Exception as e:
        print("3 ERR", e)
