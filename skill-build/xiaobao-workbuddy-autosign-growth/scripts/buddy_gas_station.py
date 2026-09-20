#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Buddy 加油站 API 链路 —— 签到 / 盲盒 / 猫猫旅行（零第三方依赖）。

设计要点（均为实测结论）：
- 签到接口走登录态里的 ``auth.domain`` 且带 ``/v2`` 前缀；
- 盲盒与旅行接口走 ``https://www.workbuddy.cn`` 且**不带** /v2 前缀（用错一律 404）；
- 已签到返回 ``code=10001`` 属幂等跳过，不是错误；
- 盲盒能量不足、旅行每日派遣达上限时只跳过，绝不硬刷。

用法：
    python buddy_gas_station.py                 # 签到 + 盲盒 + 旅行闭环
    python buddy_gas_station.py --check-only    # 只查询
    python buddy_gas_station.py --account KEY   # 指定账号（需同目录 config.json）

退出码：0 成功 / 1 业务失败 / 2 登录态失效。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

AUTH_RELPATH = os.path.join("CodeBuddyExtension", "Data", "Public", "auth",
                            "workbuddy-desktop.info")
GROWTH_HOSTS = ("https://www.workbuddy.cn", "https://www.codebuddy.cn")


# --------------------------------------------------------------------------- #
# 登录态
# --------------------------------------------------------------------------- #
def find_auth_files() -> List[str]:
    """定位本机登录态文件（可能有多份）。"""
    roots = []
    for key in ("LOCALAPPDATA", "APPDATA"):
        val = os.environ.get(key)
        if val:
            roots.append(val)
    roots.append(os.path.expanduser("~"))
    found: List[str] = []
    for root in roots:
        p = os.path.join(root, AUTH_RELPATH)
        if os.path.isfile(p) and p not in found:
            found.append(p)
    return found


def load_auth(path: Optional[str] = None) -> Dict[str, Any]:
    """读取登录态 JSON，返回 ``auth`` 字典。"""
    p = path or (find_auth_files() or [None])[0]
    if not p or not os.path.isfile(p):
        raise SystemExit("未找到登录态文件，请先在 WorkBuddy 客户端登录")
    with open(p, "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
    auth = data.get("auth") or {}
    if not auth.get("accessToken"):
        raise SystemExit("登录态里没有 accessToken，请重新登录客户端")
    return auth


def load_accounts(cfg_path: str) -> List[Dict[str, Any]]:
    """读取多账号配置 ``config.json``（与 buddy-auto 项目同构）。"""
    if not os.path.isfile(cfg_path):
        return []
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    return [a for a in (cfg.get("accounts") or []) if a.get("enabled", True)]


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def request_json(url: str, token: str, method: str = "GET",
                 body: Optional[Dict[str, Any]] = None, timeout: int = 25
                 ) -> Tuple[int, Dict[str, Any]]:
    """发 JSON 请求。返回 (http_status, 解析后的响应体)；非 2xx 也尽量解析响应体。"""
    payload = json.dumps(body if body is not None else {}).encode() if method == "POST" else None
    req = urllib.request.Request(url, method=method, data=payload)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    req.add_header("x-codebuddy-request", "1")
    req.add_header("x-client-platform", "web")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:  # 已签到等情况会返回 400，需读响应体
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:200]}
    try:
        return 200, json.loads(raw)
    except Exception:
        return 200, {"raw": raw[:200]}


def growth_request(path: str, token: str, method: str = "GET",
                   body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """请求成长中心接口：主机逐个兜底（travel 域名与签到域名不是同一个）。"""
    last = ""
    for host in GROWTH_HOSTS:
        _st, res = request_json(host + path, token, method, body)
        if isinstance(res, dict) and res.get("code") == 0:
            return res
        last = json.dumps(res, ensure_ascii=False)[:120]
    raise RuntimeError("成长接口失败：%s" % last)


# --------------------------------------------------------------------------- #
# 业务动作
# --------------------------------------------------------------------------- #
def do_checkin(auth: Dict[str, Any], check_only: bool) -> Dict[str, Any]:
    """查询/领取每日签到积分。"""
    host = "https://" + str(auth.get("domain") or "www.workbuddy.cn")
    token = auth["accessToken"]
    _st, st = request_json(host + "/v2/billing/meter/checkin-activity-status",
                           token, "POST", {})
    d = (st or {}).get("data") or {}
    if d.get("today_checked_in"):
        return {"action": "checkin", "code": "already_signed",
                "reason": "今日已签，连续 %s 天，累计 %s" % (d.get("streak_days"),
                                                            d.get("total_credits")),
                "data": d}
    if check_only:
        return {"action": "checkin", "code": "not_signed",
                "reason": "今日未签（本次只查询）", "data": d}
    _st2, r2 = request_json(host + "/v2/billing/meter/daily-checkin", token, "POST", {})
    if r2.get("code") in (0, None):
        return {"action": "checkin", "code": "claimed",
                "reason": "签到成功 +%s 积分" % ((r2.get("data") or {}).get("credit")
                                                 or d.get("daily_credit") or 0),
                "data": r2.get("data") or d}
    if r2.get("code") == 10001:
        return {"action": "checkin", "code": "already_signed",
                "reason": "今日已签（幂等跳过）", "data": d}
    return {"action": "checkin", "code": "failed", "reason": json.dumps(r2, ensure_ascii=False)[:160]}


def do_blindbox(token: str, check_only: bool) -> Dict[str, Any]:
    """能量够就开盲盒；不够如实跳过。"""
    q = growth_request("/activity/growth/buddy/quota", token)
    d = q.get("data") or {}
    cost = int(d.get("cost_per_open") or 0)
    bal = int(d.get("balance") or 0)
    affordable = int(d.get("affordable") or 0)
    if check_only:
        return {"action": "blindbox", "code": "quota",
                "reason": "能量 %d，单次消耗 %d，可开 %d 次" % (bal, cost, affordable),
                "data": d}
    if affordable <= 0:
        return {"action": "blindbox", "code": "not_enough_energy",
                "reason": "能量不足（%d/%d），本次不开" % (bal, cost), "data": d}
    opened = 0
    for _ in range(min(affordable, int(d.get("max_open_count") or 1))):
        r = growth_request("/activity/growth/buddy/open", token, "POST", {})
        opened += 1
        if r.get("code") not in (0, None):
            break
    return {"action": "blindbox", "code": "opened",
            "reason": "开启盲盒 %d 次（消耗 %d 能量）" % (opened, cost * opened),
            "data": {"opened": opened}}


def do_travel(token: str, check_only: bool, location: Optional[int] = None) -> Dict[str, Any]:
    """先领已到达奖励，再在空闲且未达每日上限时派遣。"""
    def status() -> Dict[str, Any]:
        return growth_request("/activity/growth/buddy/travel/status", token).get("data") or {}

    d = status()
    state = d.get("state")
    notes: List[str] = []
    if state == "arrived":
        if check_only:
            notes.append("已到达待领取（本次只查询）")
        else:
            growth_request("/activity/growth/buddy/travel/claim", token, "POST", {})
            notes.append("已领取到达奖励")
            d = status()
            state = d.get("state")
    if state == "idle":
        if d.get("daily_limit_reached"):
            notes.append("今日派遣已达上限，跳过")
        elif check_only:
            notes.append("空闲可派（本次只查询）")
        else:
            import random
            loc = int(location or random.randint(1, 4))
            growth_request("/activity/growth/buddy/travel/depart", token, "POST",
                           {"location_id": loc})
            notes.append("已派往地点 %d" % loc)
            d = status()
    elif state == "traveling":
        notes.append("旅行中，等待到达（无召回接口）")
    return {"action": "travel", "code": state or "unknown",
            "reason": "；".join(notes) or "状态 %s" % state, "data": d}


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def run_one(auth: Dict[str, Any], check_only: bool, location: Optional[int]) -> Dict[str, Any]:
    """对单个登录态跑完整 API 链路。"""
    token = auth["accessToken"]
    out: Dict[str, Any] = {"nickname": (load_accounts_safe(auth)),
                           "steps": []}
    out["steps"].append(do_checkin(auth, check_only))
    out["steps"].append(do_blindbox(token, check_only))
    out["steps"].append(do_travel(token, check_only, location))
    out["ok"] = all(s.get("code") not in ("failed",) for s in out["steps"])
    return out


def load_accounts_safe(auth: Dict[str, Any]) -> str:
    """取昵称用于日志展示（缺失时返回空串，不影响主流程）。"""
    return str(auth.get("nickname") or "")


def main(argv: Optional[List[str]] = None) -> int:
    """命令行入口。"""
    ap = argparse.ArgumentParser(description="Buddy 加油站 API 链路（签到/盲盒/旅行）")
    ap.add_argument("--check-only", action="store_true", help="只查询，不领取不派遣")
    ap.add_argument("--account", help="指定账号 key（需同目录 config.json）")
    ap.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                     "config.json"),
                    help="多账号配置文件路径")
    ap.add_argument("--location", type=int, choices=[1, 2, 3, 4], help="派遣地点 1-4")
    args = ap.parse_args(argv)

    if args.account:
        accounts = load_accounts(args.config)
        acc = next((a for a in accounts if a.get("key") == args.account), None)
        if not acc:
            print("配置里没有账号 %s" % args.account)
            return 1
        cred_path = os.path.join(os.path.dirname(os.path.abspath(args.config)),
                                 str(acc.get("cred_file") or ""))
        if not os.path.isfile(cred_path):
            print("凭证文件不存在：%s" % cred_path)
            return 2
        with open(cred_path, "r", encoding="utf-8") as fh:
            auth = (json.load(fh).get("auth") or {})
        if not auth.get("accessToken"):
            print("凭证里没有 accessToken")
            return 2
        result = run_one(auth, args.check_only, args.location)
    else:
        auth = load_auth()
        result = run_one(auth, args.check_only, args.location)

    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
