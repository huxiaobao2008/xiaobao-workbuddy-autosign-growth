# -*- coding: utf-8 -*-
"""查看账号剩余积分（真实余额）。用法：python _credits.py [key ...]"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auto_buddy as A  # noqa: E402

if __name__ == "__main__":
    cfg = A.load_config()
    accts = {a["key"]: a for a in cfg.get("accounts", [])}
    keys = sys.argv[1:] or list(accts)
    out = {}
    for k in keys:
        acc = accts.get(k)
        if not acc:
            out[k] = {"err": "未知账号"}
            continue
        cred, err = A.load_cred(acc)
        if not cred:
            out[k] = {"err": err}
            continue
        b = A.query_balance(cred)
        out[k] = {"remaining": b.get("remaining"), "used": b.get("used"),
                  "total": b.get("total"), "paid": b.get("is_paid_user"),
                  "err": b.get("err")}
    print(json.dumps(out, ensure_ascii=False, indent=2))
