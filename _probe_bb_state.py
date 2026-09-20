# -*- coding: utf-8 -*-
"""只读探针：验证盲盒（energy/quota）与旅行（status/config）接口的真实响应。"""
import json

import requests

import auto_buddy as core

HOSTS = ["https://www.workbuddy.cn", "https://www.codebuddy.cn"]
PATHS = [
    "GET /activity/growth/energy",
    "GET /activity/growth/buddy/quota",
    "GET /activity/growth/buddy/info",
    "GET /activity/growth/buddy/travel/status",
    "GET /activity/growth/buddy/travel/config",
]


def call(host, path, token, method="GET"):
    url = host + path
    try:
        r = requests.request(method, url, headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "x-codebuddy-request": "1",
            "x-client-platform": "web",
        }, timeout=20)
        try:
            body = r.json()
        except Exception:
            body = r.text[:120]
        return r.status_code, body
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, str(e)[:100])


cfg = core.load_config()
acct = next((a for a in cfg.get("accounts") or [] if a.get("key") == "account_g"), None)
cred, err = core.load_cred(acct)
token = (cred.get("auth") or {}).get("accessToken")
print("account_g token ok:", bool(token))

for host in HOSTS:
    print("=== HOST", host)
    for spec in PATHS:
        method, path = spec.split(" ")
        st, body = call(host, path, token, method)
        if isinstance(body, dict):
            brief = json.dumps({k: body.get(k) for k in ("code", "msg", "data")},
                               ensure_ascii=False)[:400]
        else:
            brief = str(body)[:200]
        print("   %-48s %s  %s" % (path, st, brief))
    # 只试第一个能通的 host
    print()
