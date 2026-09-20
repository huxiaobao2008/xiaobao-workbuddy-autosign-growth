# -*- coding: utf-8 -*-
"""测试：召唤专家 -> 发一条消息 -> 看进度是否 +1。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_driver as U  # noqa: E402
import ui_tasks as T   # noqa: E402

SUMMON_JS = r"""
(async (idx) => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  for (let a = 0; a < 3; a++) {
    if (document.querySelector('.ec-list-tab')) break;
    const e = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
      .find(b => T(b).indexOf('专家') !== -1);
    realClick(e); await sleep(1600);
    for (let i = 0; i < 20; i++) { if (document.querySelector('.ec-list-tab')) break; await sleep(700); }
  }
  const tab = Array.from(document.querySelectorAll('.ec-list-tab')).find(x => T(x) === '专家');
  if (tab && tab.className.toString().indexOf('is-active') === -1) { realClick(tab); await sleep(2600); }
  const cards = Array.from(document.querySelectorAll('.ec-expert-card'));
  if (!cards.length) return { ok: false, err: 'no cards' };
  const card = cards[idx] || cards[0];
  const btn = card.querySelector('.ec-card-summon-btn');
  if (!btn) return { ok: false, err: 'no summon btn' };
  realClick(btn);
  await sleep(4200);
  const ed = document.querySelector('[contenteditable=true]');
  return { ok: true, name: T(card).slice(0, 30),
           composer: !!ed,
           edText: ed ? (ed.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 120) : null,
           chips: Array.from(document.querySelectorAll('.phrase-content-wrapper')).map(x => (x.innerText || '').trim()) };
})
"""

if __name__ == "__main__":
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    prompt = sys.argv[2] if len(sys.argv) > 2 else "用一句话介绍你自己的能力。"
    do_del = "--del" in sys.argv

    print("== 当前状态 ==")
    print(json.dumps(U.status(), ensure_ascii=False))

    before = U.stable_task_titles()
    print("before_titles:", json.dumps(before, ensure_ascii=False))

    print("== 召唤 ==")
    s = U.js("(async () => { const f = " + SUMMON_JS + ";\n return await f(%d); })()" % idx,
             timeout=120)
    print(json.dumps(s, ensure_ascii=False, indent=2))
    if not (isinstance(s, dict) and s.get("ok")):
        sys.exit(1)

    print("== 打字 ==")
    print(json.dumps(U.type_text(prompt), ensure_ascii=False))

    print("== 发送 ==")
    print(json.dumps(U.js("(async () => { const s = send(); return s; })()", timeout=40),
                     ensure_ascii=False))

    # 等一会儿让对话跑起来
    for i in range(6):
        time.sleep(5)
        st = U.js("(() => { const v=document.querySelector('.cr-message-list-viewport');"
                  " return { view: !!v, proc: v?!!v.querySelector('.cr-agent--processing'):false,"
                  "  len: v?(v.innerText||'').length:0,"
                  "  stop: (document.querySelector('button.cr-send-button')||{}).className }; })()")
        print("t+%ds" % ((i + 1) * 5), json.dumps(st, ensure_ascii=False))

    after = U.stable_task_titles()
    new = [t for t in after if t not in set(before)]
    print("new_titles:", json.dumps(new, ensure_ascii=False))

    if do_del and len(new) == 1:
        U.js("(async () => { await openNewTask(); await sleep(600); return true; })()", timeout=60)
        print("deleted:", json.dumps(U.delete_conversation(new[0]), ensure_ascii=False))
