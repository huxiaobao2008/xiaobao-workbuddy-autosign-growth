# -*- coding: utf-8 -*-
"""逐步截图 + 全页文本 dump，看清「召唤专家团」到底弹了什么、停在哪。

用法: python _probe_visual.py [idx] [team|expert]
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import ui_driver as U       # noqa: E402
import ui_tasks as UT       # noqa: E402

IDX = int(sys.argv[1]) if len(sys.argv) > 1 else 6
KIND = sys.argv[2] if len(sys.argv) > 2 else "team"

BODY = r"""(() => {
  const t = (document.body.innerText || '').replace(/\n{2,}/g, '\n').trim();
  return { len: t.length, txt: t.slice(0, 1200),
           chips: document.querySelectorAll('.phrase-content-wrapper').length,
           editors: document.querySelectorAll('[contenteditable=true]').length };
})()"""


def snap(tag, gap=0):
    if gap:
        time.sleep(gap)
    print("\n############ %s ############" % tag, flush=True)
    try:
        print(json.dumps(U.shot("_shot_%s.png" % tag), ensure_ascii=False), flush=True)
    except Exception as e:
        print("shot fail: %s" % e, flush=True)
    try:
        d = U.js(BODY, timeout=40)
        print(json.dumps(d, ensure_ascii=False)[:1700], flush=True)
    except Exception as e:
        print("body fail: %s" % e, flush=True)


pick_fn = UT._as_fn(UT.EXPERT_PICK_STEP)
U.js(UT.EXPERT_ENTER_STEP, timeout=90)
time.sleep(7)
U.js("(async () => { const f = %s; return await f(%s, null, 0); })()" % (pick_fn, json.dumps(KIND)),
     timeout=90)
time.sleep(4)
snap("1_tab")

r = U.js(UT.EXPERT_TEAM_OPEN_MODAL_STEP % IDX, timeout=120)
print("[open-modal] %s" % json.dumps(r, ensure_ascii=False)[:300], flush=True)
snap("2_modal", 2)

r = U.js(UT.EXPERT_TEAM_MODAL_SUMMON_STEP, timeout=120)
print("[summon] %s" % json.dumps(r, ensure_ascii=False)[:400], flush=True)
snap("3_after_summon", 1)
snap("4_after_3s", 3)
