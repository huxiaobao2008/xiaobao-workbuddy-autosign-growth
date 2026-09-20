#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
只读工具：打印各账号的成长任务矩阵。

用途：驱动客户端 UI 完成任务时，删除会话前/后核对进度有没有被带掉。
不接取、不领取、不写任何状态文件。

用法：
    python task_status.py                 # 全部账号
    python task_status.py account_a       # 指定账号
    python task_status.py account_a --grep template_5
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auto_buddy as core   # noqa: E402
import tasks as T           # noqa: E402


def main():
    argv = sys.argv[1:]
    grep = None
    keys = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--grep":
            i += 1
            grep = argv[i] if i < len(argv) else None
        elif a.startswith("--grep="):
            grep = a.split("=", 1)[1]
        elif not a.startswith("--"):
            keys.append(a)
        i += 1

    cfg = core.load_config()
    accounts = cfg.get("accounts") or []
    keys = keys or [a.get("key") for a in accounts]

    for k in keys:
        acct = next((a for a in accounts if a.get("key") == k), None)
        if not acct:
            print("!! 未知账号 %s" % k)
            continue
        cred, err = core.load_cred(acct)
        if err:
            print("== %s 凭证不可用：%s" % (k, err))
            continue
        lst, err = T.fetch_tasks(cred, cfg)
        if err:
            print("== %s 拉取失败：%s" % (k, err))
            continue
        prof, _ = T.fetch_profile(cred, cfg)
        s = T.summarize(lst)
        print("== %s（%s） 完成 %d/%d  可领 %d 项 / %d 分  潜在 %d 分"
              % (k, acct.get("label") or acct.get("uid"), s["done"], s["total"],
                 s["claimable"], s["pending_credit"], s["potential_credit"]))
        for t in lst:
            if grep and grep not in (t["code"] or "") and grep not in (t["title"] or ""):
                continue
            print("   %-9s %-10s %-26s %s" % (t["progress_text"], t["status_label"],
                                              t["code"], t["title"]))
        if prof:
            print("   档案：%s" % {x: prof.get(x) for x in
                                 ("level", "completed_task_count", "total_task_count")
                                 if x in prof})
    return 0


if __name__ == "__main__":
    sys.exit(main())
