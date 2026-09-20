#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐账号读取侧边栏会话（带 reload 强制刷新 + 稳定判定），用于核对是否误删。

为什么要 reload：实测客户端在切换账号后，左下角昵称和侧边栏列表都是**延迟重绘**的。
只按写入后的短暂等待去读，可能读到上一个账号的数据 —— 据此做删除会误删。
所以核对时必须 reload，让渲染进程重新拉一次列表。

用法：
    python verify_convos.py                 # 全部账号
    python verify_convos.py account_d,account_e
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import account_switch as AS   # noqa: E402
import ui_driver as U         # noqa: E402

ALL = ["account_a", "account_b", "account_c", "account_d", "account_e", "account_f"]


def stable_convos(gap=4.0, tries=6):
    """读会话列表，直到连续两次结果一致（避免读到重绘中的旧数据）。"""
    prev = None
    for _ in range(tries):
        cur = U.conversations()
        if prev is not None and json.dumps(cur, ensure_ascii=False) == json.dumps(prev, ensure_ascii=False):
            return cur
        prev = cur
        time.sleep(gap)
    return prev


def main():
    argv = sys.argv[1:]
    keys = [x for x in (argv[0].split(",") if argv and not argv[0].startswith("--") else ALL) if x]
    main_key, _ = AS.current_key()
    out = {}
    try:
        for k in keys:
            sw = AS.switch_to(k, reload=True)
            info = {"ok": sw.get("ok"), "menu": (sw.get("after") or {}).get("menu")}
            if not sw.get("ok"):
                out[k] = {"switch_err": sw.get("err"), "menu": info["menu"]}
                continue
            info["convos"] = stable_convos()
            out[k] = info
    finally:
        if main_key:
            AS.switch_to(main_key, reload=True)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
