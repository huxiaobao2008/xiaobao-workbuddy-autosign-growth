# -*- coding: utf-8 -*-
"""只读探针：从成长中心前端 bundle 里提取盲盒/能量/旅行相关接口路径。"""
import re

import requests

BASE = ("https://download.codebuddy.cn/web/usercenter/"
        "e64b8fb4bc34aa55029abb007f83b311b08261f3/assets/")
NAMES = [
    "growthSpace-CCYzF8bt.js",
    "growthSpace-hZkeVNUN.js",
    "config-BxH8baql.js",
    "AllTasksPage-C6azPaoi.js",
]
KEY = re.compile(r"growth|buddy|box|energy|travel|checkin|blind", re.I)
PATH_RE = re.compile(r"""["'`](/[A-Za-z0-9_\-/{}.]{3,90})["'`]""")

sess = requests.Session()
sess.headers["User-Agent"] = "Mozilla/5.0"

for name in NAMES:
    try:
        js = sess.get(BASE + name, timeout=60).text
    except Exception as exc:  # 网络问题不影响其它文件
        print("=== %s FETCH FAIL %s" % (name, exc))
        continue
    print("=== %s (%d bytes)" % (name, len(js)))
    seen = set()
    for m in PATH_RE.finditer(js):
        h = m.group(1)
        if KEY.search(h) and h not in seen:
            seen.add(h)
            print("   ", h)
    for kw in ("盲盒", "energy", "travel", "box/open"):
        i = js.find(kw)
        if i >= 0:
            print("   [%s] %s" % (kw, js[max(0, i - 120):i + 200].replace("\n", " ")[:300]))
