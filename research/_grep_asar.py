#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在客户端 app.asar 里搜「切换账号」相关入口实现。"""
import sys

P = r"D:\Program Files\WorkBuddy\resources\app.asar"
PATS = ["switchAccount", "切换其他账号", "使用其他账号", "其他账号", "账号列表",
        "已登录账号", "switch-account", "C_PAGE_SET_COOKIE", "accountList", "accounts"]


def main():
    with open(P, "rb") as f:
        data = f.read()
    print("asar size", len(data))
    for s in PATS:
        b = s.encode("utf-8")
        idxs = []
        st = 0
        while len(idxs) < 5:
            i = data.find(b, st)
            if i < 0:
                break
            idxs.append(i)
            st = i + 1
        print("=== %s : %d hits" % (s, len(idxs)))
        for i in idxs:
            seg = data[max(0, i - 150):i + 210].decode("utf-8", "replace").replace("\n", " ")
            print("    ", seg[:340])
    return 0


if __name__ == "__main__":
    sys.exit(main())
