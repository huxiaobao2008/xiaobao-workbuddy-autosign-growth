#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 asar 里搜专家列表相关 API 路径。"""
import re
import sys

P = r"D:\Program Files\WorkBuddy\resources\app.asar"


def main():
    with open(P, "rb") as f:
        data = f.read()
    txt = data.decode("utf-8", "replace")
    pats = [
        r"/v\d+/[a-z0-9/_-]*expert[a-z0-9/_-]*",
        r"/[a-z0-9/_-]*expert[a-z0-9/_-]*/(list|search|detail|categories|scene)[a-z0-9/_-]*",
        r"expertMarket[a-zA-Z0-9/_-]*",
        r"MARKETPLACE[a-zA-Z_]*",
        r"marketplace[a-zA-Z0-9/_.-]*",
    ]
    seen = set()
    for p in pats:
        hits = re.findall(p, txt, re.I)
        for h in hits:
            if len(h) < 4 or len(h) > 90:
                continue
            if h in seen:
                continue
            seen.add(h)
        print("=== %s : %d unique" % (p, len(seen)))
    for h in sorted(seen):
        print("   ", h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
