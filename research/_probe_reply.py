#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断：用 GLM-5.2 建一条会话并**保留**，读回 DOM 里标注的模型名与回复内容。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import account_switch as AS   # noqa: E402
import ui_driver as U         # noqa: E402

READ = r"""
(async () => {
  const v = document.querySelector('.cr-message-list-viewport');
  if (!v) return { err: 'no viewport' };
  const out = { text: (v.innerText || '').replace(/\n{2,}/g, '\n').slice(0, 2500),
                modelish: [] };
  document.querySelectorAll('[class*=model]').forEach(e => {
    const t = (e.innerText || '').replace(/\s+/g, ' ').trim();
    if (t && t.length < 60) out.modelish.push({ cls: e.className.toString().slice(0, 70), t });
  });
  return out;
})()
"""


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "account_d"
    model = sys.argv[2] if len(sys.argv) > 2 else "GLM-5.2"
    sw = AS.switch_to(key, reload=False)
    print("switch ok=%s menu=%s" % (sw.get("ok"), (sw.get("after") or {}).get("menu")))
    if not sw.get("ok"):
        return 1
    try:
        r = U.set_model(U.CHEAP_MODELS[0])
        print("reset model:", json.dumps(r, ensure_ascii=False))
        run = U.run_task("", "用一句话说明什么是递归。只给答案。", model=model,
                         max_wait=240, delete_after=False, use_template=False)
        print("run ok=%s prepare=%s" % (run.get("ok"), json.dumps(run.get("prepare"), ensure_ascii=False)))
        print("created_title=%r" % run.get("created_title"))
        import time
        time.sleep(2)
        dom = U.js(READ, timeout=60)
        print(json.dumps(dom, ensure_ascii=False, indent=2)[:4000])
    finally:
        back = AS.switch_to("account_a", reload=False)
        print("switched back ok=%s menu=%s" % (back.get("ok"), (back.get("after") or {}).get("menu")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
