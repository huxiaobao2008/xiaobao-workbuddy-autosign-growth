#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""试 create_canvas：设计创意场景下发一条设计需求并轮询。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import account_switch as AS   # noqa: E402
import ui_driver as U         # noqa: E402
import batch_runner as BR     # noqa: E402

PRE = """
(async () => {
  const c = await closeOverlays();
  const s = await setScene('设计创意');
  return { closed: c.closed, scene: s };
})()
"""

PROMPT = sys.argv[2] if len(sys.argv) > 2 else "帮我做一个简单的个人名片网页，一页就够，风格简洁。"
MODEL = sys.argv[3] if len(sys.argv) > 3 else "Hy3"


def show(key, code):
    m, err = BR.fetch_map(key)
    if err:
        return err
    t = m.get(code) or {}
    return "%s/%s %s" % ((t.get("progress") or {}).get("current"),
                         (t.get("progress") or {}).get("target"), t.get("status"))


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "account_f"
    code = "create_canvas"
    print("BEFORE", show(key, code))
    sw = AS.switch_to(key, reload=False)
    print("switch ok=%s menu=%s" % (sw.get("ok"), (sw.get("after") or {}).get("menu")))
    if not sw.get("ok"):
        return 1
    try:
        r = U.run_task("", PROMPT, model=MODEL, max_wait=420,
                       delete_after=False, use_template=False, pre_js=PRE)
        for k in ("home", "pre", "cleared", "typed", "prepare", "convoAfter"):
            print("%-10s %s" % (k, json.dumps(r.get(k), ensure_ascii=False)[:400]))
        print("ok=%s err=%s created=%r" % (r.get("ok"), r.get("err"), r.get("created_title")))
        run = r.get("run") or {}
        print("run.done=%s reason=%s final=%s" % (run.get("done"), run.get("reason"),
                                                  json.dumps(run.get("final") or {}, ensure_ascii=False)))
        print("run.log=", json.dumps((run.get("log") or [])[:8], ensure_ascii=False))
        print("DOM=", json.dumps(U.js("""(() => {
          const ed = document.querySelector('[contenteditable=true]');
          const b = document.querySelector('button.cr-send-button');
          const pill = Array.from(document.querySelectorAll('.wb-scene-tabs__pill'))
            .filter(p => p.className.toString().indexOf('--active') !== -1).map(p=>p.innerText.trim());
          return { edText: ed ? (ed.innerText||'').slice(0,120) : null,
                   edCls: ed ? ed.className.toString().slice(0,80) : null,
                   sendCls: b ? b.className.toString().slice(0,100) : null,
                   sendDisabled: b ? b.disabled : null,
                   activeScene: pill,
                   view: !!document.querySelector('.cr-message-list-viewport') };
        })()""", timeout=30), ensure_ascii=False))
    finally:
        print("AFTER ", show(key, code))
        back = AS.switch_to("account_a", reload=False)
        print("back ok=%s" % back.get("ok"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
