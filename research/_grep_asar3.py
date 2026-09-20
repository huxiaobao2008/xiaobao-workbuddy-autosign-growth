#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜 renderer 里与账号切换/退出登录相关的可见文案与组件。"""
import sys

P = r"D:\Program Files\WorkBuddy\resources\app.asar"
PATS = ["switchToAccount", "退出登录", "logoutOverlay", "个人主页",
        "personAccountList", "账号与安全", "登录其他账号"]


def main():
    with open(P, "rb") as f:
        data = f.read()
    for s in PATS:
        b = s.encode("utf-8")
        idxs = []
        st = 0
        while len(idxs) < 4:
            i = data.find(b, st)
            if i < 0:
                break
            idxs.append(i)
            st = i + 1
        print("=== %s : %d hits" % (s, len(idxs)))
        for i in idxs:
            seg = data[max(0, i - 200):i + 260].decode("utf-8", "replace").replace("\n", " ")
            print("    ", seg[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
