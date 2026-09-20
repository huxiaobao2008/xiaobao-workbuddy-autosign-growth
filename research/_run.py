#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用探针运行器：切到指定账号 → 跑一个 JS 文件 → 切回主号。

用法：python _run.py <账号key> <js文件> [--no-switch]
JS 文件里直接写 (async () => { ... })() 的**函数体**，可用 ui_driver.js() 注入的
PRELUDE 工具：realClick / sleep / txt / exact / has / deepest / openNewTask /
pageState / convoItems / taskTitles 等。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import account_switch as AS   # noqa: E402
import ui_driver as U         # noqa: E402
import batch_runner as BR     # noqa: E402


def prog(key, codes):
    out = {}
    for c in codes:
        if c == "all":
            continue
        m, err = BR.fetch_map(key)
        if err:
            out[c] = "err:" + err
            continue
        t = m.get(c) or {}
        out[c] = "%s/%s %s" % ((t.get("progress") or {}).get("current"),
                               (t.get("progress") or {}).get("target"), t.get("status"))
    return out


def main():
    argv = [a for a in sys.argv[1:]]
    if len(argv) < 2:
        print(__doc__)
        return 1
    key, jsfile = argv[0], argv[1]
    no_switch = "--no-switch" in argv
    codes = []
    for i, a in enumerate(argv):
        if a == "--code" and i + 1 < len(argv):
            codes = [x for x in argv[i + 1].split(",") if x]
    with open(os.path.join(HERE, jsfile), encoding="utf-8") as f:
        body = f.read()

    if codes:
        print("BEFORE ", json.dumps(prog(key, codes), ensure_ascii=False))
    if not no_switch:
        sw = AS.switch_to(key, reload=False)
        print("switch ok=%s menu=%s" % (sw.get("ok"), (sw.get("after") or {}).get("menu")))
        if not sw.get("ok"):
            return 1
    try:
        r = U.js(body, timeout=300)
        print(json.dumps(r, ensure_ascii=False, indent=2)[:20000])
    finally:
        if codes:
            print("AFTER  ", json.dumps(prog(key, codes), ensure_ascii=False))
        if not no_switch:
            back = AS.switch_to("account_a", reload=False)
            print("back ok=%s menu=%s" % (back.get("ok"), (back.get("after") or {}).get("menu")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
