#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""试「召唤专家」：召唤第 N 位专家 -> 直接发送预填引导语 -> 核对 expert_5。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import account_switch as AS   # noqa: E402
import ui_driver as U         # noqa: E402
import batch_runner as BR     # noqa: E402

PRE_TMPL = """
(async () => {
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 44);
  await closeOverlays();
  const entry = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
    .find(b => T(b).indexOf('专家') !== -1);
  if (!entry) return { err: 'no expert entry' };
  realClick(entry);
  // 轮询等专家卡片出现（专家中心内容异步加载，固定 sleep 不够）
  let cards = [];
  for (let i = 0; i < 25; i++) {
    await sleep(1000);
    cards = Array.from(document.querySelectorAll('.ec-expert-card'))
      .filter(c => c.querySelector('.ec-card-summon-btn'));
    if (cards.length) break;
  }
  if (!cards.length) return { err: 'no card after wait', n: 0 };
  const card = cards[%d] || cards[0];
  const name = (card.querySelector('[class*=ec-card-title], [class*=title]') || {}).innerText || T(card);
  const btn = card.querySelector('.ec-card-summon-btn');
  realClick(btn);
  await sleep(4000);
  const ed = document.querySelector('[contenteditable=true]');
  return { ok: true, idx: %d, nCards: cards.length, name: name.replace(/\\s+/g, ' ').trim().slice(0, 30),
           prefilled: ed ? (ed.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 90) : null,
           chips: Array.from(document.querySelectorAll('.phrase-content-wrapper')).map(x => (x.innerText||'').trim()) };
})()
"""


def show(key, code):
    m, err = BR.fetch_map(key)
    if err:
        return err
    t = m.get(code) or {}
    return "%s/%s %s" % ((t.get("progress") or {}).get("current"),
                         (t.get("progress") or {}).get("target"), t.get("status"))


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "account_f"
    idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    code = sys.argv[3] if len(sys.argv) > 3 else "expert_5"
    print("BEFORE", show(key, code))
    sw = AS.switch_to(key, reload=False)
    print("switch ok=%s" % sw.get("ok"))
    if not sw.get("ok"):
        return 1
    try:
        r = U.run_task("", None, model=None, max_wait=300, delete_after=False,
                       use_template=False, pre_js=PRE_TMPL % (idx, idx), keep_input=True)
        print("pre=", json.dumps(r.get("pre") or {}, ensure_ascii=False))
        print("cleared=", json.dumps(r.get("cleared") or {}, ensure_ascii=False))
        print("ok=%s created=%r" % (r.get("ok"), r.get("created_title")))
        run = r.get("run") or {}
        print("run.done=%s reason=%s final=%s" % (run.get("done"), run.get("reason"),
                                                  json.dumps(run.get("final") or {}, ensure_ascii=False)))
        print("run.log.head=", json.dumps((run.get("log") or [])[:4], ensure_ascii=False))
    finally:
        time.sleep(4)
        print("AFTER ", show(key, code))
        back = AS.switch_to("account_a", reload=False)
        print("back ok=%s" % back.get("ok"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
