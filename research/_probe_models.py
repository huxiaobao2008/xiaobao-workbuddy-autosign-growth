#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断：列出模型选择器条目 + 当前触发按钮上的模型标注。只读，不改任何东西。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import account_switch as AS   # noqa: E402
import ui_driver as U         # noqa: E402

JS = r"""
(async () => {
  await openNewTask();
  await sleep(1200);
  const out = { trigger: null, items: [], pickers: 0 };
  const trig = document.querySelector('.cr-model-selector__trigger');
  out.trigger = trig ? (trig.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 80) : null;
  out.pickers = document.querySelectorAll('.cr-model-selector, [class*=model-selector]').length;
  if (trig) {
    realClick(trig);
    await sleep(1500);
    document.querySelectorAll('.cr-model-selector__item').forEach(it => {
      const nm = it.querySelector('.cr-model-selector__item-name');
      out.items.push({ name: nm ? (nm.innerText || '').trim() : null,
                       text: (it.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 80) });
    });
  }
  return out;
})()
"""


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "account_d"
    back_to = sys.argv[2] if len(sys.argv) > 2 else "account_a"
    sw = AS.switch_to(key, reload=False)
    print("switch ok=%s menu=%s" % (sw.get("ok"), (sw.get("after") or {}).get("menu")))
    if not sw.get("ok"):
        return 1
    try:
        r = U.js(JS, timeout=90)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    finally:
        back = AS.switch_to(back_to, reload=False)
        print("switched back ok=%s menu=%s" % (back.get("ok"), (back.get("after") or {}).get("menu")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
