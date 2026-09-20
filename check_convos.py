#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出各账号侧边栏会话（只读）。--del <标题关键字> 可删指定会话。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auto_buddy as core     # noqa: E402
import account_switch as AS   # noqa: E402
import ui_driver as U         # noqa: E402


def main():
    argv = sys.argv[1:]
    keys = [x for x in (argv[0].split(",") if argv and not argv[0].startswith("--")
                        else "account_a,account_b,account_c,account_d,account_e,account_f".split(",")) if x]
    grab = "--del" in argv
    kw = argv[argv.index("--del") + 1] if grab else None

    main_key, _ = AS.current_key()
    out = {}
    try:
        for k in keys:
            sw = AS.switch_to(k, reload=False)
            if not sw.get("ok"):
                out[k] = {"switch_err": sw.get("err")}
                continue
            if grab and kw:
                # 先等侧边栏稳定，否则可能读到上一个账号的旧列表 → 找不到目标会话
                U.stable_task_titles()
                out[k] = {"delete": U.delete_conversation(kw)}
            else:
                U.stable_task_titles()
                out[k] = {"convos": U.conversations()}
    finally:
        if main_key:
            AS.switch_to(main_key, reload=False)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
