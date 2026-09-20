#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对照实验：切场景前后各打一次字，定位 insertText 失效的原因。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import account_switch as AS   # noqa: E402
import ui_driver as U         # noqa: E402
import cdp as C               # noqa: E402

PROBE = """(() => {
  const e = document.querySelector('[contenteditable=true]');
  const ae = document.activeElement;
  return { hasEd: !!e,
           activeTag: ae ? ae.tagName.toLowerCase() : null,
           activeCls: ae ? (ae.className||'').toString().slice(0,60) : null,
           focused: document.hasFocus(),
           edText: e ? (e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,60) : null };
})()"""


def report(tag):
    cdp, _ = C.connect()
    try:
        return {tag: cdp.evaluate(PROBE, timeout=20)}
    finally:
        cdp.close()


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "account_f"
    sw = AS.switch_to(key, reload=False)
    print("switch ok=%s" % sw.get("ok"))
    if not sw.get("ok"):
        return 1
    try:
        out = {}
        U.js("(async () => { await closeOverlays(); await openNewTask(); await sleep(1500); return true; })()", timeout=60)
        out["A_before_typing"] = report("A")["A"]
        out["A_cleared"] = U.clear_input()
        out["A_typed"] = U.type_text("测试一")
        out["A_after"] = report("A2")["A2"]

        out["B_clear2"] = U.clear_input()
        out["B_scene"] = U.js("(async () => await setScene('设计创意'))()", timeout=90)
        out["B_before_typing"] = report("B")["B"]
        out["B_cleared"] = U.clear_input()
        out["B_typed"] = U.type_text("测试二")
        out["B_after"] = report("B2")["B2"]

        # C：切回日常办公再试
        out["C_scene"] = U.js("(async () => await setScene('日常办公'))()", timeout=90)
        out["C_clear"] = U.clear_input()
        out["C_typed"] = U.type_text("测试三")
        out["C_after"] = report("C2")["C2"]
        print(json.dumps(out, ensure_ascii=False, indent=2))
    finally:
        back = AS.switch_to("account_a", reload=False)
        print("back ok=%s" % back.get("ok"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
