#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 renderer 包里搜 permissionConfirm / requestSubmit / getSubmitError 的实现。"""
import sys

P = r"D:\Program Files\WorkBuddy\resources\app.asar"
PATS = ["permissionConfirm", "requestSubmit", "getSubmitError", "permissionConfirmContext",
        "允许完全访问"]


def main():
    with open(P, "rb") as f:
        data = f.read()
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
        print("\n=== %s : %d hits ===" % (s, len(idxs)))
        for i in idxs:
            seg = data[max(0, i - 300):i + 500].decode("utf-8", "replace").replace("\n", " ")
            print("   @%d %s" % (i, seg[:750]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
