#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""继续搜：切换账号 UI 入口 / 登录页 switch 模式。"""
import sys

P = r"D:\Program Files\WorkBuddy\resources\app.asar"
PATS = ["Switch account", "switchAccountUrl", "show_type", "openSwitchAccount",
        "scenario/switch-account", "addAccount", "Add account", "add-account",
        "logoutAndSwitch", "account-switch"]


def main():
    with open(P, "rb") as f:
        data = f.read()
    for s in PATS:
        b = s.encode("utf-8")
        idxs = []
        st = 0
        while len(idxs) < 6:
            i = data.find(b, st)
            if i < 0:
                break
            idxs.append(i)
            st = i + 1
        print("=== %s : %d hits" % (s, len(idxs)))
        for i in idxs:
            seg = data[max(0, i - 160):i + 200].decode("utf-8", "replace").replace("\n", " ")
            print("    ", seg[:330])
    return 0


if __name__ == "__main__":
    sys.exit(main())
