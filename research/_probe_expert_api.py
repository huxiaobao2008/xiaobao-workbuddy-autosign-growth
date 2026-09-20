# -*- coding: utf-8 -*-
"""直接查专家列表接口，判断「暂无内容」是账号问题还是接口问题。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auto_buddy as A  # noqa: E402

PATHS = [
    "/v2/open-platform/experts",
    "/v2/open-platform/experts/search",
]

if __name__ == "__main__":
    keys = sys.argv[1:] or ["account_f", "account_a"]
    cfg = A.load_config()
    accts = {a["key"]: a for a in cfg.get("accounts", [])}
    for k in keys:
        acc = accts.get(k)
        if not acc:
            print(k, "未知账号")
            continue
        cred, err = A.load_cred(acc)
        if not cred:
            print(k, "凭证错误", err)
            continue
        for p in PATHS:
            for method in ("GET", "POST"):
                try:
                    code, res = A.api(cred, p, method=method,
                                      body={} if method == "POST" else None)
                except Exception as e:
                    print(k, p, method, "EXC", type(e).__name__, str(e)[:80])
                    continue
                d = res.get("data") if isinstance(res, dict) else None
                n = None
                if isinstance(d, list):
                    n = len(d)
                elif isinstance(d, dict):
                    for kk in ("list", "items", "experts", "records", "total"):
                        if kk in d:
                            v = d[kk]
                            n = len(v) if isinstance(v, list) else v
                            break
                print(k, method, p, "http=%s biz=%s" % (code, res.get("code")),
                      "n=%s" % n, "msg=%s" % str(res.get("msg", ""))[:60])
    print("done")
