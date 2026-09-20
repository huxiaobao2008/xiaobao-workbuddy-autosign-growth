# -*- coding: utf-8 -*-
"""诊断专家团的真实 UI 契约：卡片按钮、召唤后是否出现确认弹窗/协作入口。

只做「进入专家团 → 点召唤 → 观察 DOM」，不发送消息，不新建会话。
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import ui_driver as U      # noqa: E402
import ui_tasks as UT      # noqa: E402

DUMP_OVERLAYS = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const hits = [];
  document.querySelectorAll('div,section,aside').forEach(el => {
    const c = (el.className || '').toString();
    if (/overlay|dialog|confirm|modal|popup/i.test(c)) {
      const r = el.getBoundingClientRect();
      if (r.width > 60 && r.height > 40) {
        hits.push({ cls: c.slice(0, 110), txt: T(el).slice(0, 260),
                    btns: Array.from(el.querySelectorAll('button')).map(b => T(b)).slice(0, 8),
                    tracks: Array.from(el.querySelectorAll('[data-track-id]'))
                              .map(b => b.getAttribute('data-track-id')).slice(0, 8) });
      }
    }
  });
  return { n: hits.length, hits: hits.slice(0, 6),
           edLen: (document.querySelector('[contenteditable=true]') || {}).innerText
                    ? document.querySelector('[contenteditable=true]').innerText.length : 0 };
})()
"""

CARDS_DUMP = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const cards = Array.from(document.querySelectorAll('.ec-expert-card'));
  return {
    n: cards.length,
    tabs: Array.from(document.querySelectorAll('.ec-list-tab')).map(x => T(x)),
    first: cards[0] ? {
      txt: T(cards[0]).slice(0, 300),
      btns: Array.from(cards[0].querySelectorAll('button')).map(b => ({
        t: T(b).slice(0, 40), cls: (b.className || '').toString().slice(0, 80),
        track: b.getAttribute('data-track-id'), disabled: b.disabled })),
      tracks: Array.from(cards[0].querySelectorAll('[data-track-id]'))
                .map(b => b.getAttribute('data-track-id')).slice(0, 10)
    } : null
  };
})()
"""


def main():
    print("[1] enter expert center", flush=True)
    print("   ", json.dumps(UT.EXPERT_ENTER_STEP and U.js(UT.EXPERT_ENTER_STEP, timeout=60),
                           ensure_ascii=False), flush=True)

    print("[2] pick tab = 专家团", flush=True)
    pick = UT._expert_steps("team", None, 0)[0][1]
    print("   ", json.dumps(U.js(pick, timeout=60), ensure_ascii=False), flush=True)
    time.sleep(5)

    print("[3] cards", flush=True)
    print("   ", json.dumps(U.js(CARDS_DUMP, timeout=60), ensure_ascii=False)[:1200], flush=True)

    print("[4] overlays BEFORE summon", flush=True)
    print("   ", json.dumps(U.js(DUMP_OVERLAYS, timeout=40), ensure_ascii=False)[:700], flush=True)

    print("[5] click 召唤 on card 0", flush=True)
    summon = UT._expert_steps("team", None, 0)[0][2]
    print("   ", json.dumps(U.js(summon, timeout=60), ensure_ascii=False), flush=True)

    for i, wait in enumerate((2, 4, 6)):
        time.sleep(wait if i == 0 else 3)
        print("[6.%d] overlays AFTER summon (+%ds)" % (i, 2 + i * 3), flush=True)
        print("   ", json.dumps(U.js(DUMP_OVERLAYS, timeout=40), ensure_ascii=False)[:900], flush=True)

    print("[7] composer / current view", flush=True)
    print("   ", json.dumps(U.js(r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const ed = document.querySelector('[contenteditable=true]');
  return {
    edText: ed ? T(ed).slice(0, 200) : null,
    chips: Array.from(document.querySelectorAll('[class*=chip],[class*=tag]'))
             .map(x => T(x)).filter(Boolean).slice(0, 8),
    agentCount: document.querySelectorAll('.cr-agent').length,
    sendBtn: (() => { const b = document.querySelector('button.cr-send-button');
                      return b ? { cls: (b.className||'').toString().slice(0,70), disabled: b.disabled } : null; })()
  };
})()
""", timeout=40), ensure_ascii=False)[:800], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
