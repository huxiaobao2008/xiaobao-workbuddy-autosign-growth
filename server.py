#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
buddy-auto 本地网页管理界面（零第三方依赖，标准库 http.server）。
复用 auto_buddy.py 的配置读写、凭证抓取、任务执行与日志，不另起一套数据层。

启动：python auto_buddy.py --ui [--port 8765]
只监听 127.0.0.1，不对外暴露；任何响应都不含 token。
"""
import json
import os
import socket
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

import auto_buddy as core
import tasks
import account_switch as AS  # 真正的客户端登录切换（原子替换登录文件 + CDP 校验）
import subprocess            # 后台跑 run_all.py（一键全自动）

BASE_DIR = core.BASE_DIR
UI_FILE = os.path.join(BASE_DIR, "ui.html")
LOCK = threading.Lock()

# /api/state 要拉每个账号的任务/档案/积分/余额（网络 IO）。账号一多，串行会拖到 70 秒+，
# 页面卡「加载中」、其它请求还得排队等 LOCK。这里并行化 + 短 TTL 缓存兜底。
STATE_TTL = 5.0
STATE_CACHE = {"ts": 0.0, "data": None}


def _state_bust():
    """任何会改动账号/客户端状态的动作之后清缓存，让页面立刻拿到新数据。"""
    STATE_CACHE["ts"] = 0.0
    STATE_CACHE["data"] = None


def _pmap(fn, items, workers=12):
    """并发 map（网络 IO 密集），保持输入顺序。"""
    items = list(items)
    if not items:
        return []
    w = max(1, min(workers, len(items)))
    if w == 1:
        return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=w) as ex:
        return list(ex.map(fn, items))
# 当前操作的账号（点击切换后所有操作默认作用于它）
ACTIVE = {"key": ""}
# 新账号自动入库的后台巡检状态
WATCH = {"running": False, "interval": 30, "last_scan": "", "last_added": []}
# 一键全自动（run_all.py）后台进程状态
RUN_ALL_PROC = None
RUN_ALL_LOG = None
RUN_ALL_LOG_PATH = os.path.join(core.LOG_DIR, "run_all_server.log")

# 「停止任务」跨进程标记：server 写它，run_all / ui_driver 在检查点读它。
# 路径必须与 ui_driver.STOP_FILE 完全一致（否则两边看不到同一个文件）。
STOP_FILE = os.path.join(core.LOG_DIR, "STOP_ALL")

# 单账号「执行本账号」后台任务（点账号行触发，不阻塞 HTTP 请求）
ACCT_JOB = {"running": False, "key": "", "label": "", "tail": "",
            "result": None, "started": "", "finished": ""}
ACCT_JOB_LOG_PATH = os.path.join(core.LOG_DIR, "run_account_server.log")
ACCT_BUDGET = 15 * 60


def run_all_status():
    """读取一键全自动的实时状态：是否在跑 + 日志尾部。"""
    global RUN_ALL_PROC
    tail = ""
    try:
        with open(RUN_ALL_LOG_PATH, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
        tail = "\n".join(lines[-50:])
    except Exception:
        pass
    running = bool(RUN_ALL_PROC and RUN_ALL_PROC.poll() is None)
    return {"running": running, "log_path": RUN_ALL_LOG_PATH, "tail": tail,
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


def _clear_stop():
    """清掉「停止」标记 —— 每次开始新任务前调用，保证新一轮能正常跑。"""
    try:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
    except Exception:
        pass


def _stopping():
    return os.path.exists(STOP_FILE)


def action_stop(payload):
    """停止任务：先写跨进程停止标记，让 run_all / UI 驱动**在下一个检查点收手**；
    若进程仍不肯退出（卡在不会返回的调用里），短暂等待后强杀兜底。"""
    _state_bust()   # 与其他动作一致：清状态缓存，前端紧接着的查询立刻拿到停止后的新状态
    try:
        os.makedirs(core.LOG_DIR, exist_ok=True)
        with open(STOP_FILE, "w", encoding="utf-8") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        return {"ok": False, "error": "写停止标记失败：%s: %s" % (type(e).__name__, e)}

    killed = []
    # 1) 一键全自动（独立子进程）
    global RUN_ALL_PROC
    if RUN_ALL_PROC and RUN_ALL_PROC.poll() is None:
        for _ in range(30):          # 最多等 15s 让它在检查点优雅退出
            if RUN_ALL_PROC.poll() is not None:
                break
            time.sleep(0.5)
        if RUN_ALL_PROC.poll() is None:
            try:
                RUN_ALL_PROC.terminate()
                killed.append("run_all")
            except Exception:
                pass

    # 2) 单账号任务（后台线程）：驱动会在轮询分段处看到标记自行收手
    if ACCT_JOB.get("running"):
        killed.append("account-job")

    return {"ok": True, "stopping": True, "killed": killed,
            "message": "已发出停止指令" + ("，正在中止：%s" % "、".join(killed) if killed else "")}


def action_run_all(payload):
    """一键全自动：后台启动 run_all.py（签到+成长任务+领积分+出行），UI 轮询进度。

    进程是 server 的子进程；server 本身是用户从桌面启动器拉起的常驻进程，
    所以子进程不会被 WorkBuddy 会话的 kill-on-close Job 误杀。
    """
    global RUN_ALL_PROC, RUN_ALL_LOG
    if RUN_ALL_PROC and RUN_ALL_PROC.poll() is None:
        return {"ok": True, "running": True, "message": "一键全自动已在运行中，进度见下方日志"}
    _clear_stop()   # 新一轮开始，清掉上一轮的停止标记
    try:
        cfg = core.load_config()
        py = cfg.get("python_path") or sys.executable
        script = os.path.join(core.BASE_DIR, "run_all.py")
        os.makedirs(core.LOG_DIR, exist_ok=True)
        f = open(RUN_ALL_LOG_PATH, "wb")
        f.seek(0)
        f.truncate(0)
        RUN_ALL_LOG = f
        RUN_ALL_PROC = subprocess.Popen([py, script], cwd=core.BASE_DIR,
                                        stdout=f, stderr=subprocess.STDOUT)
        return {"ok": True, "running": True, "message": "已启动一键全自动，进度见下方",
                "pid": RUN_ALL_PROC.pid}
    except Exception as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}


# --------------------------------------------------------------------------- #
# 单账号「执行本账号」：完整流水线（签到 + 按需 UI 任务 + 领积分），后台跑不阻塞 UI
# --------------------------------------------------------------------------- #
def acct_job_status():
    """读取单账号执行的实时状态：是否在跑 + 日志尾部 + 结果。"""
    tail = ""
    try:
        with open(ACCT_JOB_LOG_PATH, "r", encoding="utf-8", errors="replace") as fh:
            tail = "\n".join(fh.read().splitlines()[-50:])
    except Exception:
        pass
    return {"running": bool(ACCT_JOB.get("running")), "key": ACCT_JOB.get("key", ""),
            "label": ACCT_JOB.get("label", ""), "tail": tail,
            "result": ACCT_JOB.get("result"),
            "started": ACCT_JOB.get("started", ""), "finished": ACCT_JOB.get("finished", "")}


def _should_skip_ui_tasks(acc, cfg):
    """该账号成长任务已全部完成（done==total）且没有待领积分时，跳过 UI 任务驱动。

    签到仍在调用方先跑。返回 (skip, reason)。
    """
    try:
        cred, err = core.load_cred(acc)
        if not cred:
            return False, ""
        tl, _ = tasks.fetch_tasks(cred, cfg)
        s = tasks.summarize(tl)
        if s.get("total") and s.get("done") == s.get("total") and not s.get("pending_credit"):
            return True, "成长任务已全部完成（%d/%d），跳过 UI 任务驱动" % (s["done"], s["total"])
    except Exception as e:
        return False, "任务状态读取失败：%s" % e
    return False, ""


def _run_account_job(key):
    """后台线程：对单个账号跑完整流水线（签到 + [按需]UI 任务 + 领积分），再切回原账号。

    已完成的账号跳过 UI 任务驱动（省时间/省额度），但签到照常。
    """
    global ACCT_JOB
    try:
        cfg = core.load_config()
        acc = next((a for a in cfg["accounts"] if a["key"] == key), None)
        if not acc:
            ACCT_JOB["result"] = {"ok": False, "error": "配置里没有账号 %s" % key}
            return
        ACCT_JOB["label"] = acc.get("label", key)
        ACCT_JOB["started"] = core.now_str()

        restore_key = None
        try:
            restore_key = AS.current_key()[0]
        except Exception:
            restore_key = None

        f = open(ACCT_JOB_LOG_PATH, "wb")
        f.seek(0)
        f.truncate(0)

        def log(m):
            line = "[%s] %s" % (core.now_str(), m)
            try:
                f.write((line + "\n").encode("utf-8"))
                f.flush()
            except Exception:
                pass
            ACCT_JOB["tail"] = line

        try:
            # 1) 签到 + 出行 + API 成长任务 + 热度（所有人每天照常）
            log("阶段一：签到 / 出行 / API 成长任务 / 热度")
            r = core.run_account(acc, cfg)
            log("签到/API: %s | %s" % (r.get("status"), r.get("reason")))

            skip, why = _should_skip_ui_tasks(acc, cfg)
            ui_got = 0
            if skip:
                log(why)
            else:
                # 2) UI 类任务（自动切号 + 当场领取）
                import batch_runner as BR
                codes = ["template_5", "Model_chat_GLM5.2"] + list(BR.UI_CODES)
                deadline = time.time() + ACCT_BUDGET
                out = BR.run_account(key, codes, BR.TEMPLATE_POOL, do_claim=True,
                                     do_delete=True, dry=False, log=log, deadline=deadline,
                                     stop=_stopping)
                ui_got = int((out.get("claim") or {}).get("credit_got") or 0)
                log("UI 切号 ok=%s | %s" % ((out.get("switch") or {}).get("ok"),
                                           out.get("err") or "完成"))

            # 3) 收尾领取（漏领的积分补领）
            import claim_all as CA
            cr = CA.claim_account(acc, cfg, quiet=True)
            claim_got = int(cr.get("credit_got") or 0)
            log("收尾领取 %s 项 | 到账 %s 积分" % (cr.get("claimed"), claim_got))

            # 4) 服务端真相对账：不看"跑没跑"，只看服务端记的完成度。
            #    之前"UI 显示都跑完了、实际只完成 6/19"就是这个对账缺失导致的虚报。
            try:
                _cred, _e = core.load_cred(acc)
                if _cred:
                    _lst, _le = tasks.fetch_tasks(_cred, cfg)
                    if not _le:
                        _s = tasks.summarize(_lst)
                        _undone = [t for t in _lst
                                   if not (t.get("status") in ("claimed", "completed")
                                           or ((t.get("progress") or {}).get("target")
                                               and ((t.get("progress") or {}).get("current") or 0)
                                               >= (t.get("progress") or {})["target"]))]
                        log("服务端进度 %s/%s｜未完成 %d 项：%s"
                            % (_s.get("done"), _s.get("total"), len(_undone),
                               "、".join("%s(%s)" % (t.get("title"), t.get("status"))
                                         for t in _undone[:8]) or "无"))
                        ACCT_JOB["result"]["server_done"] = _s.get("done")
                        ACCT_JOB["result"]["server_total"] = _s.get("total")
                        ACCT_JOB["result"]["undone"] = [t.get("code") for t in _undone]
            except Exception as _e:
                log("服务端进度对账失败：%s" % str(_e)[:80])

            ACCT_JOB["result"] = {"ok": True, "api": r.get("status"), "skipped_ui": skip,
                                   "skip_reason": why, "credit_got": ui_got + claim_got,
                                   "ui_got": ui_got, "claim_got": claim_got}
        finally:
            if restore_key:
                try:
                    AS.switch_to(restore_key, reload=False)
                    log("已切回原账号 %s" % restore_key)
                except Exception as e:
                    log("切回原账号失败：%s" % e)
            try:
                f.close()
            except Exception:
                pass
    except Exception as e:
        ACCT_JOB["result"] = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
    finally:
        ACCT_JOB["running"] = False
        ACCT_JOB["finished"] = core.now_str()


def action_run_account(payload):
    """点账号「执行本账号」：后台跑该账号完整流水线，UI 轮询进度。"""
    global ACCT_JOB
    if ACCT_JOB.get("running"):
        return {"ok": False, "error": "已有账号正在执行，请稍候（进度见「本账号执行」卡片）"}
    key = (payload or {}).get("key", "")
    if not key:
        return {"ok": False, "error": "缺少 key"}
    with LOCK:
        cfg = core.load_config()
        acc = next((a for a in cfg["accounts"] if a["key"] == key), None)
    if not acc:
        return {"ok": False, "error": "列表里没有 %s" % key}
    ACCT_JOB.update({"running": True, "key": key, "label": acc.get("label", key),
                     "result": None, "tail": "启动中…",
                     "started": core.now_str(), "finished": ""})
    threading.Thread(target=_run_account_job, args=(key,), daemon=True).start()
    return {"ok": True, "message": "已启动 %s 的完整执行（签到+成长任务+领积分）" % acc.get("label", key),
            "key": key}


def action_set_mode(payload):
    """切换手动/自动模式，持久化到 config.json（auto_mode=true 表示自动）。"""
    with LOCK:
        cfg = core.load_config()
        cfg["auto_mode"] = bool((payload or {}).get("auto", False))
        core.save_config(cfg)
    return {"ok": True, "auto_mode": cfg["auto_mode"],
            "message": "已切到%s模式" % ("自动" if cfg["auto_mode"] else "手动")}


def watch_new_accounts(interval=30):
    """后台巡检：任何新账号在本机登录成功后，自动入库并纳入自动执行。"""
    WATCH.update({"running": True, "interval": interval})
    while True:
        try:
            added, skipped = core.auto_sync_accounts()
            WATCH["last_scan"] = core.now_str()
            if added:
                WATCH["last_added"] = added
                print(f"[{core.now_str()}] 自动入库 {len(added)} 个新账号："
                      + "、".join(a["label"] for a in added))
        except Exception as e:
            WATCH["last_scan"] = f"{core.now_str()}（巡检异常：{e}）"
        time.sleep(interval)


# --------------------------------------------------------------------------- #
# 状态组装
# --------------------------------------------------------------------------- #
def account_state(acc, with_tasks=True):
    """单个已配置账号：凭证状态 + 积分 + 成长任务列表 + 最近一次执行结果。"""
    cred, err = core.load_cred(acc)
    item = {
        "key": acc["key"], "label": acc.get("label", ""), "uid": acc.get("uid", ""),
        "nickname": acc.get("nickname", ""), "enabled": acc.get("enabled", True),
        "times": acc.get("times", []), "cred_ok": cred is not None,
        "cred_error": err or "", "credits": {}, "balance": {}, "tasks": [], "task_summary": {}, "profile": {},
    }
    if cred:
        days = core.cred_expiry_days(cred)
        item["cred_expiry_days"] = round(days, 1) if days is not None else None
        item["cred_expired"] = bool(days is not None and days <= 0)
        item["credits"] = core.query_credits(cred)
        item["balance"] = core.query_balance(cred)
        if with_tasks:
            tl, terr = tasks.fetch_tasks(cred, core.load_config())
            prof, perr = tasks.fetch_profile(cred, core.load_config())
            item["tasks"] = tl
            item["task_summary"] = tasks.summarize(tl)
            item["profile"] = prof
            item["task_error"] = terr or perr or ""
    return item


def discovered_state(cfg):
    """本机登录态里发现的账号：是否已添加 + 积分（只读查询，不领取）。"""
    warnings = []
    if not os.path.isdir(core.AUTH_DIR):
        return [], ["没找到 WorkBuddy 登录态目录，本机可能从未登录过客户端：" + core.AUTH_DIR]

    in_cfg = {a.get("uid"): a["key"] for a in cfg["accounts"]}

    def one(d):
        err = ""
        try:
            data = core.read_auth_file(d["path"])
            if data:
                credits = core.query_credits(data)
            else:
                credits = {"err": "登录态文件解析失败"}
        except Exception as e:
            credits = {"err": f"{type(e).__name__}: {e}"}
            err = f"{d['nickname'] or d['uid']} 读取失败：{e}"
        row = {
            "uid": d["uid"], "nickname": d["nickname"], "phone": d["phone"],
            "saved_at": d["saved_at"], "expiry_days": d["expiry_days"],
            "expired": d["expired"], "credits": credits,
            "in_config": d["uid"] in in_cfg, "config_key": in_cfg.get(d["uid"], ""),
        }
        return row, err

    results = _pmap(one, core.discover_accounts(), workers=12)
    out = [r for r, _ in results]
    warnings = [e for _, e in results if e]
    if not out:
        warnings.append(f"登录态目录里没读到任何可用账号（文件损坏或字段缺失）：{core.AUTH_DIR}")
    return out, warnings


def client_current_state():
    """客户端**当前实际**登录的账号（通过 CDP 读左下角 .user-menu-trigger 昵称）。

    UI 驱动成长任务只能作用于客户端当前登录的那个账号，
    所以这个状态是「切换登录」操作的核心依据。客户端未开/未带调试端口时 reachable=False。
    """
    try:
        key, menu = AS.current_key()
        return {"reachable": True, "key": key or "", "menu": menu or "", "error": ""}
    except Exception as e:
        return {"reachable": False, "key": "", "menu": "",
                "error": "%s: %s" % (type(e).__name__, e)}


def build_state(use_cache=True):
    if use_cache and STATE_CACHE["data"] is not None \
            and (time.time() - STATE_CACHE["ts"]) < STATE_TTL:
        return STATE_CACHE["data"]
    with LOCK:
        cfg = core.load_config()
    # 并发拉各账号（网络 IO 密集）；discovered 与 client_current 同时并行跑
    accounts = _pmap(lambda a: account_state(a), cfg["accounts"], workers=12)
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_disc = ex.submit(discovered_state, cfg)
        f_cc = ex.submit(client_current_state)
        discovered, warnings = f_disc.result()
        client_current = f_cc.result()
    for a in accounts:
        a["is_current_client"] = bool(client_current.get("reachable")) \
            and a["key"] == client_current.get("key")

    total = sum((a["credits"] or {}).get("total_credits") or 0 for a in accounts)
    signed = sum(1 for a in accounts if (a["credits"] or {}).get("signed"))
    remaining = 0.0
    remaining_unknown = []
    for a in accounts:
        bal = a.get("balance") or {}
        if bal.get("err"):
            remaining_unknown.append(a["label"])
        else:
            remaining += bal.get("remaining") or 0.0
        if not a["cred_ok"]:
            warnings.append(f"{a['label']} 无有效凭证：{a['cred_error']}")
        elif a.get("cred_expired"):
            warnings.append(f"{a['label']} 凭证已过期，请点「登录/续期」")
        elif a.get("cred_expiry_days") is not None and a["cred_expiry_days"] < 7:
            warnings.append(f"{a['label']} 凭证 {a['cred_expiry_days']:.0f} 天后过期")

    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "accounts": accounts,
        "discovered": discovered,
        "warnings": warnings,
        "totals": {"accounts": len(accounts), "signed_today": signed, "total_credits": total,
                   "remaining_credits": round(remaining, 2),
                   "remaining_unknown": remaining_unknown},
        "client_exe": next((p for p in core.CLIENT_EXE_CANDIDATES if p and os.path.exists(p)), ""),
        "schedule": cfg.get("schedule", {}),
        "client_current": client_current,
        "run_all": run_all_status(),
        "active_key": ACTIVE["key"] or (accounts[0]["key"] if accounts else ""),
        "watch": dict(WATCH),
        "auto_add_new_accounts": cfg.get("auto_add_new_accounts", True),
        "auto_mode": cfg.get("auto_mode", False),
        "stopping": _stopping(),
        "acct_job": acct_job_status(),
    }
    STATE_CACHE["ts"] = time.time()
    STATE_CACHE["data"] = data
    return data


# --------------------------------------------------------------------------- #
# 动作
# --------------------------------------------------------------------------- #
def action_add(payload):
    uid = (payload or {}).get("uid", "").strip()
    if not uid:
        return {"ok": False, "error": "缺少 uid"}
    with LOCK:
        acc, msg = core.add_account_by_uid(uid, label=(payload or {}).get("label"))
    if not acc:
        return {"ok": False, "error": msg}
    return {"ok": True, "message": msg, "key": acc["key"]}


def action_run(payload):
    """执行签到与成长任务：不传 key 则执行全部（等价于一键切换/批量执行）。"""
    with LOCK:
        cfg = core.load_config()
        key = (payload or {}).get("key")
        results = []
        for a in cfg["accounts"]:
            if not a.get("enabled", True):
                continue
            if key and a["key"] != key:
                continue
            r = core.run_account(a, cfg)
            r["ts"] = core.now_str()
            r["date"] = core.today_str()
            r["trigger"] = "ui"
            core.append_run(r)
            cred, _ = core.load_cred(a)
            tl = tasks.fetch_tasks(cred, cfg)[0] if cred else []
            gt = (r.get("tasks", {}).get("growth_tasks") or {})
            results.append({
                "key": r["account"], "label": r.get("label", ""), "status": r["status"],
                "reason": r.get("reason", ""),
                "steps": gt.get("steps", []),
                "task_summary": tasks.summarize(tl),
                "balance": {"before": gt.get("balance_before"), "after": gt.get("balance_after"),
                            "delta": gt.get("balance_delta"), "error": gt.get("balance_error", ""),
                            "credit_got": gt.get("credit_got", 0)},
                "skipped_paid": gt.get("skipped_paid", []),
                "failed_tasks": gt.get("failed_tasks", []),
                "credits": core.query_credits(cred) if cred else {},
            })
        core.save_json(core.LATEST_JSON, {"ts": core.now_str(), "results": results})
    if not results:
        return {"ok": False, "error": "没有可执行的启用账号"}
    return {"ok": True, "message": f"已执行 {len(results)} 个账号", "results": results}


def action_capture(payload):
    """单个账号的登录入口：本机有它的登录态就直接抓，没有就提示先扫码登录。"""
    payload = payload or {}
    with LOCK:
        cfg = core.load_config()
        acc = next((a for a in cfg["accounts"] if a["key"] == payload.get("key")), None)
        if not acc:
            return {"ok": False, "error": f"列表里没有 {payload.get('key')}"}
        src = next((d for d in core.discover_accounts() if d["uid"] == acc.get("uid")), None)
        if src:
            rc, msg = core.capture(acc, source=src["path"])
            return {"ok": rc == 0, "message": msg, "error": "" if rc == 0 else msg}
        rc, msg = core.capture(acc)  # 兜底：抓当前客户端登录态
        if rc == 0:
            return {"ok": True, "message": msg}
        return {"ok": False, "error": msg, "need_login": True,
                "hint": "本机没有该账号的登录态，请打开客户端扫码登录后重试"}


def action_capture_all(payload):
    with LOCK:
        ok, skipped = core.capture_all_possible()
    return {"ok": not skipped, "message": f"已续期 {len(ok)} 个：{', '.join(ok) or '无'}",
            "skipped": skipped}


def action_open_client(payload):
    ok, msg = core.open_client()
    return {"ok": ok, "message": msg, "error": "" if ok else msg}


def action_remove(payload):
    with LOCK:
        ok, msg = core.remove_account((payload or {}).get("key", ""))
    return {"ok": ok, "message": msg, "error": "" if ok else msg}


def action_toggle(payload):
    payload = payload or {}
    with LOCK:
        ok, msg = core.set_enabled(payload.get("key", ""), payload.get("enabled", True))
    return {"ok": ok, "message": msg, "error": "" if ok else msg}


def action_task(payload):
    """单个成长任务的操作：接取(accept) / 领取(claim) / 两者(both)。串行执行。"""
    payload = payload or {}
    key, code = payload.get("key", ""), payload.get("code", "")
    action = payload.get("action", "both")
    if not key or not code:
        return {"ok": False, "error": "缺少 key 或 code"}
    if not tasks.SERIAL_LOCK.acquire(blocking=True, timeout=60):
        return {"ok": False, "error": "已有执行在进行中（串行保护），请稍后重试"}
    try:
        with LOCK:
            cfg = core.load_config()
            acc = next((a for a in cfg["accounts"] if a["key"] == key), None)
        if not acc:
            return {"ok": False, "error": f"列表里没有 {key}"}
        cred, err = core.load_cred(acc)
        if err:
            return {"ok": False, "error": err, "need_login": True}
        steps = []
        if action in ("accept", "both"):
            ok, msg, _ = tasks.accept_task(cred, code, cfg)
            steps.append({"task": code, "step": "accept",
                          "status": "success" if ok else ("fail" if ok is False else "skip"), "reason": msg})
        if action in ("claim", "both"):
            ok, msg, _ = tasks.claim_task(cred, code, cfg)
            steps.append({"task": code, "step": "claim",
                          "status": "success" if ok else ("fail" if ok is False else "skip"), "reason": msg})
        failed = [s for s in steps if s["status"] == "fail"]
        return {"ok": not failed, "steps": steps,
                "message": "；".join(f"{s['step']}:{s['reason']}" for s in steps),
                "error": "；".join(s["reason"] for s in failed)}
    finally:
        tasks.SERIAL_LOCK.release()


def action_switch(payload):
    """点击账号即切换：程序内切到该账号，并按配置决定是否写回客户端登录态。"""
    payload = payload or {}
    key = payload.get("key", "")
    if not key:                      # 传空表示取消当前选中（收起任务面板）
        ACTIVE["key"] = ""
        return {"ok": True, "message": "已收起", "info": {}}
    with LOCK:
        ok, msg, info = core.switch_account(key, write_client=bool(payload.get("write_client")))
    if ok:
        ACTIVE["key"] = key
    return {"ok": ok, "message": msg, "error": "" if ok else msg, "info": info}


def action_client_switch(payload):
    """真正切换客户端登录账号：原子替换登录文件 + 轮询校验界面昵称。

    与 action_switch（仅程序内选择/展开任务面板）不同，这里会**改动客户端登录态**，
    因此必须客户端带调试端口启动且已登录某个账号。切换到目标账号后，
    UI 驱动的「成长任务」就会在该账号下执行。
    """
    payload = payload or {}
    key = (payload or {}).get("key", "")
    if not key:
        return {"ok": False, "error": "缺少 key"}
    with LOCK:
        try:
            # 手动「切换登录」走 reload=False + 6 秒轮询：服务端不会长时间阻塞，
            # 浏览器 fetch 不会超时；同时保留登录文件 uid 兜底——即使界面昵称
            # 还没重绘，只要文件写对就报成功，几秒内菜单会自己刷成新账号。
            r = AS.switch_to(key, reload=False, verify=True, verify_max_sec=6)
        except Exception as e:
            return {"ok": False, "need_client": True,
                    "error": "切换失败：客户端可能未打开或未带调试端口（%s: %s）" % (type(e).__name__, e),
                    "hint": "请先双击 restart-cdp.cmd 启动带调试端口的客户端，或用「打开客户端登录」扫码登录后再切换"}
    if r.get("ok"):
        after = r.get("after") or {}
        if r.get("menu_pending"):
            msg = r.get("msg") or "登录已切换，界面昵称可能稍后刷新"
        else:
            msg = "已切换并校验成功（界面昵称：%s）" % (after.get("menu") or "—")
        return {"ok": True,
                "message": msg,
                "error": "",
                "info": {k: r.get(k) for k in ("target", "want_uid", "before", "after", "wrote_uid")}}
    return {"ok": False,
            "error": r.get("err") or "切换后界面昵称未变，校验失败",
            "info": {k: r.get(k) for k in ("target", "before", "after", "wrote_uid")},
            "hint": "登录文件已写入但界面昵称未变，请稍等后点「刷新」确认；"
                    "或双击 restore-main-account.cmd 回到主号"}


def action_sync(payload):
    """手动触发一次新账号自动入库（强制重新扫描，不读缓存）。

    返回里带上诊断数字，方便一眼看出「扫描为 0」到底是真没有新号、
    还是登录态目录里确实读不到（用户反馈过这个歧义）。
    """
    with LOCK:
        added, skipped = core.auto_sync_accounts()
        found = core.discover_accounts()
        cfg = core.load_config()
    _state_bust()          # 关键：入库后清缓存，否则前端最多 5s 内还是旧列表
    dirs = core.auth_scan_dirs()
    return {
        "ok": True,
        "message": "新入库 %d 个账号（本机登录态共扫到 %d 个账号）" % (len(added), len(found)),
        "added": added,
        "skipped": skipped,
        "found": [{"uid": d["uid"], "nickname": d["nickname"], "phone": d["phone"],
                   "file": d["file"]} for d in found],
        "scan_dirs": dirs,
        "configured": len(cfg["accounts"]),
    }


ACTIONS = {
    "add": action_add,
    "run": action_run,
    "capture": action_capture,
    "capture-all": action_capture_all,
    "open-client": action_open_client,
    "remove": action_remove,
    "toggle": action_toggle,
    "task": action_task,
    "switch": action_switch,
    "client-switch": action_client_switch,
    "run-all": action_run_all,
    "run-account": action_run_account,
    "set-mode": action_set_mode,
    "sync": action_sync,
    "stop": action_stop,
}


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 静音默认访问日志
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/ui", "/index.html"):
            try:
                with open(UI_FILE, encoding="utf-8") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except Exception as e:
                self._send(500, f"界面文件读取失败：{e}", "text/plain; charset=utf-8")
            return
        if path == "/api/state":
            try:
                self._json(build_state())
            except Exception as e:
                self._json({"ok": False, "error": f"读取状态失败：{type(e).__name__}: {e}"}, 500)
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            self._json({"error": "not found"}, 404)
            return
        name = path[len("/api/"):]
        fn = ACTIONS.get(name)
        if not fn:
            self._json({"error": f"未知动作 {name}"}, 404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        payload = {}
        if length:
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8", "replace"))
            except Exception:
                payload = {}
        try:
            result = fn(payload)
            _state_bust()   # 任何动作后清状态缓存，UI 紧接着的 reload 立刻拿新数据
            self._json(result)
        except Exception as e:
            self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)


def free_port(preferred):
    for p in [preferred] + list(range(preferred + 1, preferred + 20)):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return 0


def serve(port=8765, open_browser=True):
    port = free_port(port)
    if not port:
        print("[失败] 找不到可用端口")
        return 1
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"

    # 启动即做一次自动入库，并开后台巡检盯新账号
    try:
        added, _ = core.auto_sync_accounts()
        if added:
            print(f"[{core.now_str()}] 自动入库 {len(added)} 个新账号："
                  + "、".join(a["label"] for a in added))
    except Exception as e:
        print(f"[警告] 自动入库巡检启动失败：{e}")
    threading.Thread(target=watch_new_accounts, args=(30,), daemon=True).start()

    print(f"Buddy 账号管理界面已启动：{url}")
    print("（只监听本机，关掉这个窗口即可停止）")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    import sys
    # 支持 `server.py 8765 --no-open`：
    # 启动器（Buddy加油站一键执行.cmd）自己会 start 浏览器，如果这里再 webbrowser.open
    # 就会**一次启动开两个页面**（用户实测反馈）。所以启动器传 --no-open 抑制这里的自动打开。
    _args = sys.argv[1:]
    _port = next((int(a) for a in _args if a.isdigit()), 8765)
    _open = "--no-open" not in _args
    serve(_port, open_browser=_open)
