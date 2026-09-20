#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WorkBuddy 双账号自动执行程序
=================================
功能：
  1. 多账号独立管理：本机登录过几个号，就抓几份凭证，配置文件里各自独立开关、独立时间
  2. 每日签到（Buddy加油站）：查状态 -> 未签则领取，幂等不重复
  3. 成长计划任务：成长伙伴信息同步 + 出行到达奖励自动领取
  4. 成长热度点亮：今日未活跃时发起一次云端会话（纯 API，不碰客户端），
     点亮当日热力墙并保持连续天数
  4. 按配置时间点循环执行（Windows 计划任务驱动）
  5. 每次执行写结构化日志（成功/失败原因），异常时弹窗 + 告警日志 + 可选 webhook

用法：
  python auto_buddy.py --discover              扫描本机所有可用的登录态（找账号用）
  python auto_buddy.py --capture account_a     把当前客户端登录的账号存成 account_a 的凭证
  python auto_buddy.py --list                  列出配置账号与最近执行状态
  python auto_buddy.py --run                   执行到点的账号（计划任务调用的就是这个）
  python auto_buddy.py --run --force           忽略时间窗，执行所有启用账号
  python auto_buddy.py --run --account b       只跑指定账号
  python auto_buddy.py --check                 只查询不领取（体检用）
  python auto_buddy.py --install-scheduler     按配置注册/刷新 Windows 计划任务
  python auto_buddy.py --remove-scheduler      删除计划任务
  python auto_buddy.py --notify-test           测试提醒通道

退出码：0=全部成功或无需执行；1=存在失败；2=凭证失效/缺失（需重新登录抓取）
只读取本机登录态，不修改、不外传；任何输出中的 token 均脱敏。
"""

import argparse
import glob
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")
RUNS_LOG = os.path.join(LOG_DIR, "runs.jsonl")
LATEST_JSON = os.path.join(LOG_DIR, "latest.json")
SUMMARY_TXT = os.path.join(LOG_DIR, "summary.txt")

AUTH_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "CodeBuddyExtension", "Data", "Public", "auth",
)
CURRENT_AUTH = os.path.join(AUTH_DIR, "workbuddy-desktop.info")

# --------------------------------------------------------------------------- #
# 登录态**扫描范围**（重要，别再只扫 AUTH_DIR）
#
# 真实故障（用户反馈「手机号又登了一个号，扫描为 0，只有第一次启动才扫得到」）：
#   我们自己的切号 `account_switch.switch_to()` 会把「切换前那个账号」的活文件
#   备份到 `logs/auth_backups/auth_<时间戳>_<uid>_preswitch.info`。
#   于是新登录的账号一旦被我们切走一次，它在 AUTH_DIR 的活文件就被目标账号覆盖，
#   只剩 auth_backups 里那一份 —— 而 discover_accounts() 原来**只扫 AUTH_DIR**
#   → 从此永远扫不到它（第 17 个账号 b765cb94/19528268022 就是这样丢的）。
#   第一次启动能扫到，是因为那时还没切过号、活文件还是它。
# → 所以扫描必须把备份目录一起算进来。
# --------------------------------------------------------------------------- #
AUTH_BACKUP_DIR = os.path.join(LOG_DIR, "auth_backups")


def auth_scan_dirs():
    """所有需要扫描登录态的目录（客户端活文件目录 + 我们自己的切号备份目录）。"""
    dirs = [AUTH_DIR]
    for d in (AUTH_BACKUP_DIR, os.path.join(AUTH_DIR, "backup")):
        if os.path.isdir(d) and d not in dirs:
            dirs.append(d)
    return dirs


# WorkBuddy 客户端主程序（用于「打开客户端登录」入口）
CLIENT_EXE_CANDIDATES = [
    os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "WorkBuddy", "WorkBuddy.exe"),
    r"D:\Program Files\WorkBuddy\WorkBuddy.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "WorkBuddy", "WorkBuddy.exe"),
]

# 接口（已从客户端 app.asar 源码核实）
PATH_CHECKIN_STATUS = "/v2/billing/meter/checkin-activity-status"
PATH_CHECKIN_CLAIM = "/v2/billing/meter/daily-checkin"
PATH_GROWTH_INFO = "/v2/activity/growth/buddy/info"
PATH_GROWTH_TRAVEL_CLAIM = "/v2/activity/growth/buddy/travel/claim"
# 账户余额/剩余额度。注意：网关路由不带 /v2（与 growth 的 accept/claim 同理）
PATH_RESOURCE_SUMMARY = "/billing/meter/get-user-resource-summary"

STATUS_OK = "success"
STATUS_SKIP = "skip"
STATUS_FAIL = "fail"


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def mask(token):
    if not token:
        return "<empty>"
    return f"{token[:6]}...{token[-4:]}"


def save_config(cfg):
    save_json(CONFIG_FILE, cfg)


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_config():
    cfg = load_json(CONFIG_FILE)
    if not cfg:
        print(f"[配置错误] 找不到或无法解析 {CONFIG_FILE}")
        sys.exit(1)
    cfg.setdefault("schedule", {})
    cfg.setdefault("alert", {})
    cfg.setdefault("retry", {"attempts": 2, "backoff_seconds": 2})
    cfg.setdefault("accounts", [])
    # 配置补全：老配置缺少新任务开关时按默认补齐（只补缺失项，不改已设置的 false）
    changed = False
    for a in cfg["accounts"]:
        a.setdefault("tasks", {})
        for k, v in DEFAULT_TASKS.items():
            if k not in a["tasks"]:
                a["tasks"][k] = v
                changed = True
    if changed:
        save_config(cfg)
    return cfg


def append_run(record):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(RUNS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_alert(text):
    cfg = load_config()
    path = os.path.join(BASE_DIR, cfg["alert"].get("alert_log", "logs/alerts.log"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[{now_str()}] {text}\n")


def notify(title, message, level="error"):
    """告警通道：桌面气泡 + 告警日志 + 可选 webhook。任何一环失败都不影响主流程。"""
    cfg = load_config()
    alert = cfg.get("alert", {})
    write_alert(f"[{level}] {title} | {message}")

    if alert.get("desktop_notify", True):
        desktop_toast(title, message)

    hook = alert.get("webhook_url", "")
    if hook:
        try:
            body = json.dumps({"msgtype": "text", "text": {"content": f"{title}\n{message}"}}).encode()
            req = urllib.request.Request(hook, method="POST", data=body)
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:
            write_alert(f"[webhook 发送失败] {e}")


def desktop_toast(title, message):
    """
    Windows 系统托盘气泡提醒。
    优先用纯 Win32 API 的独立进程（notify_toast.py），失败再退回 PowerShell，
    都失败也只写告警日志，绝不影响主流程。
    """
    toast = os.path.join(BASE_DIR, "notify_toast.py")
    runners = []
    if os.path.exists(toast):
        base, ext = os.path.splitext(sys.executable)
        pythonw = base + "w" + ext  # pythonw.exe：不弹黑窗
        runners.append(pythonw if os.path.exists(pythonw) else sys.executable)
    try:
        if runners:
            subprocess.Popen(
                [runners[0], toast, title, message],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return
        raise FileNotFoundError("notify_toast.py 缺失")
    except Exception as e:
        write_alert(f"[桌面提醒降级] {e}")

    ps = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$ni = New-Object System.Windows.Forms.NotifyIcon;"
        "$ni.Icon = [System.Drawing.SystemIcons]::Warning;"
        f"$ni.BalloonTipTitle = '{title}';"
        f"$ni.BalloonTipText = '{message}';"
        "$ni.BalloonTipIcon = 'Warning';"
        "$ni.Visible = $true; $ni.ShowBalloonTip(15000);"
        "Start-Sleep -Seconds 12; $ni.Dispose()"
    )
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as e:
        write_alert(f"[桌面提醒失败] {e}")


# --------------------------------------------------------------------------- #
# 凭证
# --------------------------------------------------------------------------- #
def read_auth_file(path):
    j = load_json(path)
    if not j:
        return None
    auth = j.get("auth") or {}
    if not auth.get("accessToken") or not auth.get("domain"):
        return None
    return {"auth": auth, "account": j.get("account") or {}}


def load_cred(account):
    path = os.path.join(BASE_DIR, account["cred_file"])
    cred = load_json(path)
    if not cred:
        return None, f"凭证文件缺失：{account['cred_file']}（先登录客户端后执行 --capture {account['key']}）"
    auth = cred.get("auth") or {}
    if not auth.get("accessToken"):
        return None, "凭证内容不完整"
    if account.get("uid") and cred.get("account", {}).get("uid") and cred["account"]["uid"] != account["uid"]:
        return None, f"凭证 UID 与配置不符（凭证={cred['account']['uid']} 配置={account['uid']}）"
    return cred, None


def cred_expiry_days(cred):
    exp = (cred.get("auth") or {}).get("expiresAt")
    if not exp:
        return None
    return (exp / 1000 - time.time()) / 86400.0


def discover_accounts():
    """扫描本机保存过的所有登录态（活文件 + 客户端历史备份 + 我们自己的切号备份），
    按账号去重，返回最近的一份。

    扫描范围由 auth_scan_dirs() 决定 —— 它同时覆盖 `logs/auth_backups`，
    否则「被我们切走过一次」的新账号会永远扫不到（真实故障，见该函数注释）。
    """
    best = {}
    paths = []
    for d in auth_scan_dirs():
        paths.extend(glob.glob(os.path.join(d, "*.info")))
    for path in paths:
        data = read_auth_file(path)
        if not data:
            continue
        uid = (data.get("account") or {}).get("uid") or "unknown"
        mtime = os.path.getmtime(path)
        if uid not in best or mtime > best[uid][0]:
            best[uid] = (mtime, path, data)
    out = []
    for uid, (mtime, path, data) in sorted(best.items(), key=lambda kv: -kv[1][0]):
        acct = data.get("account") or {}
        days = cred_expiry_days(data)
        out.append({
            "uid": uid,
            "nickname": acct.get("nickname") or "",
            "phone": acct.get("phoneNumber") or "",
            "file": os.path.basename(path),
            "path": path,
            "saved_at": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "expiry_days": round(days, 1) if days is not None else None,
            "expired": bool(days is not None and days <= 0),
        })
    return out


def query_credits(cred):
    """只查询积分与签到状态，不领取。失败时返回 err 字段而不是抛异常。"""
    try:
        r = task_checkin(cred, check_only=True)
    except Exception as e:
        return {"err": f"{type(e).__name__}: {e}"}
    d = r.get("data") or {}
    # 契约：失败返回 err 而不是抛异常 —— status 用 .get，防止个别失败路径缺键时 KeyError
    _status = r.get("status")
    _err = r.get("reason", "") if _status == STATUS_FAIL else ""
    if r.get("err"):
        _err = _err or str(r.get("err"))
    return {
        "err": _err,
        "signed": d.get("today_checked_in"),
        "streak_days": d.get("streak_days"),
        "total_credits": d.get("total_credits"),
        "daily_credit": d.get("daily_credit"),
        "active": d.get("active"),
        "end_time": d.get("end_time"),
    }


def _to_float(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return 0.0


def query_balance(cred):
    """查询账户剩余额度（真实可用积分余额）。

    与 query_credits 不是一个东西：
      - query_credits.total_credits = 签到活动「累计获得」的积分
      - query_balance.remaining     = 账户里「还剩多少可用」的额度

    唯一公开来源是 /billing/meter/get-user-resource-summary 的
    Packages[].CycleRemainCapacity（单位 credits）。失败时返回 err，不抛异常。
    """
    try:
        code, res = api(cred, PATH_RESOURCE_SUMMARY)
    except Exception as e:
        return {"err": f"{type(e).__name__}: {e}"}
    if auth_error(code, res):
        return {"err": "登录态失效（401/403），需重新登录客户端并 --capture"}
    if code != 200 or res.get("code") != 0:
        return {"err": f"余额接口异常 http={code} biz={res.get('code')} msg={res.get('msg', '')}"}

    data = res.get("data") or {}
    packages, remain, total, used = [], 0.0, 0.0, 0.0
    for p in data.get("Packages") or []:
        r = _to_float(p.get("CycleRemainCapacity"))
        t = _to_float(p.get("CycleTotalCapacity"))
        u = _to_float(p.get("CycleUsedCapacity"))
        remain += r
        total += t
        used += u
        packages.append({
            "code": p.get("PackageCode", ""),
            "remain": r, "total": t, "used": u,
            "unit": p.get("CapacityUnit", "credits"),
        })
    return {
        "err": "",
        "remaining": remain,
        "total": total,
        "used": used,
        "is_paid_user": bool(data.get("IsPaidUser")),
        "packages": packages,
    }


def next_key(cfg):
    """生成不重复的账号 key：account_c、account_d……"""
    used = {a["key"] for a in cfg["accounts"]}
    i = 0
    while True:
        i += 1
        key = "account_" + chr(ord("a") + i - 1) if i <= 26 else f"account_{i}"
        if key not in used:
            return key


def add_account_by_uid(uid, label=None):
    """把本机已有的某个登录态账号加入配置，并顺带抓取凭证。返回 (account, message)。"""
    cfg = load_config()
    if any(a.get("uid") == uid for a in cfg["accounts"]):
        return None, f"该账号已在列表中（uid={uid}），无需重复添加"

    src = next((d for d in discover_accounts() if d["uid"] == uid), None)
    if not src:
        return None, f"本机没有 uid={uid} 的登录态，请先在客户端登录该账号"

    key = next_key(cfg)
    cred_file = f"accounts/{key}.cred.json"
    acc = {
        "key": key,
        "label": label or src["nickname"] or src["phone"] or key,
        "uid": uid,
        "nickname": src["nickname"],
        "cred_file": cred_file,
        "enabled": True,
        # 首个账号可能没有 times 字段 —— 逐级兜底，别让新账号入列就 KeyError
        "times": list((cfg["accounts"][0].get("times") if cfg["accounts"] else None) or ["08:00"]),
        "tasks": {"checkin": True, "growth_info": True, "growth_travel_claim": True},
    }
    cfg["accounts"].append(acc)
    save_config(cfg)

    rc, cap_msg = capture(acc, source=src["path"])
    if rc == 0:
        return acc, f"已添加 {key}（{acc['label']}）并抓取凭证"
    return acc, f"已加入列表，但凭证抓取失败：{cap_msg}；请在客户端登录该账号后点「登录/续期」"


def remove_account(key):
    cfg = load_config()
    left = [a for a in cfg["accounts"] if a["key"] != key]
    if len(left) == len(cfg["accounts"]):
        return False, f"列表里没有 {key}"
    cfg["accounts"] = left
    save_config(cfg)
    return True, f"已从列表移除 {key}（凭证文件保留，未删除）"


def set_enabled(key, enabled):
    cfg = load_config()
    acc = next((a for a in cfg["accounts"] if a["key"] == key), None)
    if not acc:
        return False, f"列表里没有 {key}"
    acc["enabled"] = bool(enabled)
    save_config(cfg)
    return True, f"{key} 已{'启用' if enabled else '停用'}"


def auto_sync_accounts(include_expired=False):
    """
    自动入库：本机登录态里出现、但配置列表里没有的账号，自动加入列表并抓凭证。
    返回 (added, skipped)；added 里的账号默认 enabled=True 且带全部默认任务，
    因此会直接纳入后续的签到与成长任务自动执行。
    """
    cfg = load_config()
    if not cfg.get("auto_add_new_accounts", True):
        return [], ["配置里关闭了自动入库（auto_add_new_accounts=false）"]
    known = {a.get("uid") for a in cfg["accounts"]}
    added, skipped = [], []
    for d in discover_accounts():
        if d["uid"] in known:
            continue
        if d.get("expired") and not include_expired:
            skipped.append(f"{d['nickname'] or d['uid']}（登录态已过期，跳过）")
            continue
        acc, msg = add_account_by_uid(d["uid"])
        if acc:
            added.append({"key": acc["key"], "label": acc["label"], "uid": d["uid"], "message": msg})
        else:
            skipped.append(f"{d['nickname'] or d['uid']}（{msg}）")
    return added, skipped


def switch_account(key, write_client=False):
    """
    切换到指定账号：程序内把该账号置为当前操作对象，并按需写回客户端登录态。
    write_client 受 config.allow_write_client_auth 控制，默认关闭（不改动客户端文件）。
    """
    cfg = load_config()
    acc = next((a for a in cfg["accounts"] if a["key"] == key), None)
    if not acc:
        return False, f"列表里没有 {key}", {}
    cred, err = load_cred(acc)
    if err:
        return False, err, {"need_login": True}

    info = {"key": key, "label": acc.get("label", ""), "nickname": acc.get("nickname", ""),
            "uid": acc.get("uid", ""), "client_written": False}
    if write_client:
        if not cfg.get("allow_write_client_auth", False):
            return True, (f"已切换到 {key}（程序内）；要连客户端一起切换，"
                          f"需先把 config.json 的 allow_write_client_auth 改为 true"), info
        try:
            if os.path.exists(CURRENT_AUTH):
                backup = CURRENT_AUTH + ".bak-" + datetime.now().strftime("%Y%m%d%H%M%S")
                with open(CURRENT_AUTH, "rb") as f1, open(backup, "wb") as f2:
                    f2.write(f1.read())
            save_json(CURRENT_AUTH, cred)
            info["client_written"] = True
            return True, f"已切换：{key} 的登录态已写回客户端（重启 WorkBuddy 后生效）", info
        except Exception as e:
            return False, f"写回客户端登录态失败：{e}", info
    return True, f"已切换到 {key}（{acc.get('label','')}）", info


def open_client():
    """打开 WorkBuddy 客户端（用于扫码登录 / 切换账号）。"""
    for p in CLIENT_EXE_CANDIDATES:
        if p and os.path.exists(p):
            try:
                subprocess.Popen([p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True, f"已启动客户端：{p}"
            except Exception as e:
                return False, f"启动客户端失败：{e}"
    return False, "没找到 WorkBuddy 客户端，请手动打开"


def capture_all_possible():
    """一键续期：所有已配置账号，只要本机还有它的登录态就直接抓取，不用重新扫码。"""
    cfg = load_config()
    found = {d["uid"]: d for d in discover_accounts()}
    ok, skipped = [], []
    for a in cfg["accounts"]:
        src = found.get(a.get("uid"))
        if not src:
            skipped.append(f"{a['key']}（本机无登录态，需扫码登录）")
            continue
        rc, cap_msg = capture(a, source=src["path"])
        if rc == 0:
            ok.append(a["key"])
        else:
            skipped.append(f"{a['key']}（{cap_msg[:40]}）")
    return ok, skipped


def capture(account, allow_mismatch=False, source=None):
    """把客户端当前登录（或指定登录态文件）的账号存为该账号的凭证。"""
    src = source or CURRENT_AUTH
    data = read_auth_file(src)
    if not data:
        return 2, (f"没读到登录态：{src}"
                   f"{'' if source else '，请先打开 WorkBuddy 客户端并登录。'}"
                   f"（可用 --discover 查看本机已保存的登录态）")
    cur_uid = (data.get("account") or {}).get("uid")
    nickname = (data.get("account") or {}).get("nickname")
    if account.get("uid") and cur_uid != account["uid"] and not allow_mismatch:
        return 2, (f"客户端当前登录的是「{nickname}」({cur_uid})，"
                   f"与配置里 {account['key']} 的 uid {account['uid']} 不一致。"
                   f"确认要覆盖请加 --allow-mismatch，或改 config.json 里的 uid。")
    save_json(os.path.join(BASE_DIR, account["cred_file"]), data)
    exp = cred_expiry_days(data)
    return 0, (f"已保存 {account['key']}（{account.get('label','')}）凭证："
               f"{nickname} / {cur_uid} / 有效期约 {exp:.0f} 天")


# --------------------------------------------------------------------------- #
# 接口调用
# --------------------------------------------------------------------------- #
def api(cred, path, method="POST", body=None):
    auth = cred["auth"]
    acct = cred.get("account") or {}
    url = f"https://{auth['domain']}{path}"
    payload = json.dumps(body if body is not None else {}).encode()
    req = urllib.request.Request(url, method=method, data=payload)
    req.add_header("Authorization", f"Bearer {auth['accessToken']}")
    if auth.get("refreshToken"):
        req.add_header("X-Refresh-Token", auth["refreshToken"])
    if acct.get("uid"):
        req.add_header("X-User-Id", acct["uid"])
    if auth.get("domain"):
        req.add_header("X-Domain", auth["domain"])
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return -1, {"error": str(e)}


def auth_error(http_code, data):
    return http_code in (401, 403) or data.get("code") in (401, 403)


# --------------------------------------------------------------------------- #
# 任务
# --------------------------------------------------------------------------- #
def task_checkin(cred, account=None, check_only=False):
    """Buddy加油站每日签到。"""
    code, res = api(cred, PATH_CHECKIN_STATUS)
    if auth_error(code, res):
        return {"status": STATUS_FAIL, "code": "auth_expired",
                "reason": "登录态失效（401/403），需重新登录客户端并 --capture"}
    if code != 200 or res.get("code") != 0:
        return {"status": STATUS_FAIL, "code": "api_error",
                "reason": f"状态接口异常 http={code} biz={res.get('code')} msg={res.get('msg','')}"}

    d = res.get("data") or {}
    info = {
        "active": d.get("active"), "today_checked_in": d.get("today_checked_in"),
        "streak_days": d.get("streak_days"), "total_credits": d.get("total_credits"),
        "daily_credit": d.get("daily_credit"), "end_time": d.get("end_time"),
    }
    if not d.get("active"):
        return {"status": STATUS_SKIP, "code": "activity_ended",
                "reason": f"本期活动已结束（截止 {d.get('end_time')}）", "data": info}
    if check_only:
        return {"status": STATUS_SKIP if not d.get("today_checked_in") else STATUS_OK,
                "code": "check_only",
                "reason": f"仅查询：今日{'已签' if d.get('today_checked_in') else '未签'}，"
                          f"连续 {d.get('streak_days')} 天，累计 {d.get('total_credits')} 积分",
                "data": info}
    if d.get("today_checked_in"):
        return {"status": STATUS_OK, "code": "already_signed",
                "reason": f"今日已签，连续 {d.get('streak_days')} 天，累计 {d.get('total_credits')} 积分",
                "data": info}

    code2, res2 = api(cred, PATH_CHECKIN_CLAIM)
    if auth_error(code2, res2):
        return {"status": STATUS_FAIL, "code": "auth_expired",
                "reason": "领取时登录态失效，需重新登录客户端并 --capture", "data": info}
    biz = res2.get("code")
    if biz == 10001:
        return {"status": STATUS_OK, "code": "already_signed",
                "reason": f"接口返回已签，连续 {d.get('streak_days')} 天，累计 {d.get('total_credits')} 积分",
                "data": info}
    if code2 != 200 or biz != 0:
        return {"status": STATUS_FAIL, "code": "claim_failed",
                "reason": f"领取失败 http={code2} biz={biz} msg={res2.get('msg','')}", "data": info}

    d2 = res2.get("data") or {}
    # today_credit 键可能存在但值为 None —— 直接 .get(默认值) 会拿到 None，
    # 文案变成「+None 积分」。逐级兜底到 0。
    gained = d2.get("today_credit") or d.get("daily_credit") or 0
    info.update({
        "gained": gained,
        "streak_days": d2.get("streak_days") or d.get("streak_days") or 0,
        "total_credits": d2.get("total_credits") or d.get("total_credits") or 0,
    })
    return {"status": STATUS_OK, "code": "claimed",
            "reason": f"签到成功 +{info['gained']} 积分，连续 {info['streak_days']} 天，累计 {info['total_credits']}",
            "data": info}


def task_growth_info(cred, account=None, check_only=False):
    """成长伙伴信息（成长计划状态同步）。"""
    code, res = api(cred, PATH_GROWTH_INFO, method="GET")
    if auth_error(code, res):
        return {"status": STATUS_FAIL, "code": "auth_expired", "reason": "登录态失效（401/403）"}
    if code != 200 or res.get("code") != 0:
        return {"status": STATUS_FAIL, "code": "api_error",
                "reason": f"成长接口异常 http={code} biz={res.get('code')} msg={res.get('msg','')}"}
    buddy = (res.get("data") or {}).get("buddy") or {}
    if not buddy:
        return {"status": STATUS_SKIP, "code": "no_buddy", "reason": "该账号暂无成长伙伴"}
    return {"status": STATUS_OK, "code": "ok",
            "reason": f"成长伙伴 {buddy.get('name')}（{buddy.get('rarity')}）状态正常",
            "data": {"name": buddy.get("name"), "rarity": buddy.get("rarity"),
                     "instance_id": buddy.get("instance_id")}}


def task_growth_travel_claim(cred, account=None, check_only=False):
    """成长计划：领取伙伴出行到达奖励积分。"""
    if check_only:
        return {"status": STATUS_SKIP, "code": "check_only", "reason": "仅查询模式，未尝试领取"}
    code, res = api(cred, PATH_GROWTH_TRAVEL_CLAIM)
    if auth_error(code, res):
        return {"status": STATUS_FAIL, "code": "auth_expired", "reason": "登录态失效（401/403）"}
    biz = res.get("code")
    msg = res.get("msg", "")
    # 已实测的"当前没有可领奖励"返回值，属于正常跳过，不算失败：
    #   not arrived yet     伙伴还在路上
    #   no unclaimed travel 已领过 / 本次出行无待领奖励
    BENIGN = ("not arrived", "no unclaimed", "already claimed", "already received",
              "nothing to claim", "no reward")
    if biz != 0 or code != 200:
        if any(k in msg.lower() for k in BENIGN):
            return {"status": STATUS_SKIP, "code": "no_pending",
                    "reason": f"暂无可领奖励（{msg}）"}
        return {"status": STATUS_FAIL, "code": "claim_failed",
                "reason": f"领取失败 http={code} biz={biz} msg={msg}"}
    return {"status": STATUS_OK, "code": "claimed", "reason": "出行到达奖励领取成功"}


def task_growth_active(cred, account=None, check_only=False):
    """成长热度：今日未活跃时发起一次云端会话点亮热力墙，顺带保持连续天数。

    依据：拆解 WorkDaddy 的 growth-active 链路 + 本项目实测 —— 该链路是纯云端会话
    （建会话 → ACP → initialize/session/prompt → 收尾），不碰客户端、不切账号、
    不写本机登录态。每成功一次会话，服务端热力分 +2 并点亮当日活跃。

    边界（已实测确认，别指望它）：它只负责「活跃 / 连续天数」，
    **不会推进 18 项成长任务的进度**——那些任务需要真实产品交互。
    """
    try:
        import growth_active as ga
    except Exception as e:
        return {"status": STATUS_FAIL, "code": "import_error",
                "reason": f"缺少 growth_active.py：{e}"}

    act = ga.today_active(cred)
    if not act.get("ok"):
        return {"status": STATUS_FAIL, "code": "api_error",
                "reason": f"成长热度查询失败：{act.get('error')}"}
    st0 = ga.streak(cred)
    days0 = st0.get("days") if st0.get("ok") else "?"
    score0 = act.get("score")

    if act.get("is_active"):
        return {"status": STATUS_SKIP, "code": "already_active",
                "reason": f"今日已活跃（连签 {days0} 天，热度分 {score0}），无需点亮",
                "data": {"streak": days0, "score": score0}}

    if check_only:
        return {"status": STATUS_SKIP, "code": "check_only",
                "reason": f"今日未活跃（连签 {days0} 天），仅查询模式未点亮",
                "data": {"streak": days0, "score": score0}}

    res = ga.activate(cred)
    if not res.get("ok"):
        return {"status": STATUS_FAIL, "code": "activate_failed",
                "reason": f"云端会话失败：{res.get('error')}"}

    # 服务端记账有 1~2 秒延迟，最多轮询 3 次确认
    act2, days2 = act, days0
    for _ in range(3):
        time.sleep(1.5)
        act2 = ga.today_active(cred)
        if act2.get("is_active"):
            days2 = (ga.streak(cred) or {}).get("days", days0)
            break
    if not act2.get("is_active"):
        return {"status": STATUS_FAIL, "code": "not_flagged",
                "reason": f"会话已发出（{res.get('seconds')}s）但服务端未记为活跃"}
    return {"status": STATUS_OK, "code": "activated",
            "reason": f"已点亮今日活跃，连签 {days2} 天（热度分 {act2.get('score')}）",
            "data": {"streak": days2, "score": act2.get("score"),
                     "seconds": res.get("seconds"),
                     "stop_reason": res.get("stop_reason")}}


def task_growth_tasks(cred, account=None, check_only=False):
    """
    成长任务清单：拉取该账号的成长任务，串行接取未接取的、领取已完成的。
    check_only=True 时只拉取并汇报，不接取不领取。
    """
    try:
        import tasks
    except Exception as e:
        return {"status": STATUS_FAIL, "code": "module_error",
                "reason": f"任务引擎加载失败：{e}"}
    acc = account or {"key": "unknown", "nickname": ""}
    result = tasks.run_tasks(cred, acc, cfg=load_config(),
                             do_accept=not check_only, do_claim=not check_only)
    out = {"status": result["status"], "code": "tasks_done",
           "reason": result["reason"], "steps": result["steps"]}
    for k in ("balance_before", "balance_after", "balance_delta", "balance_error",
              "credit_got", "skipped_paid", "skipped_other", "failed_tasks", "summary"):
        out[k] = result.get(k)
    if not check_only:
        try:
            tasks.save_state({acc.get("key", "unknown"): result["tasks"]})
        except Exception:
            pass
    return out


# 成长中心（盲盒 / 能量 / 猫猫旅行）接口主机。
# 依据 totorosir-workbuddy-checkin 技能实测：旅行接口必须用 www.workbuddy.cn 且
# **不带 /v2 前缀**（用 auth.domain 或加 /v2 一律 404）；实测 codebuddy.cn 也通，
# 最后再拿 auth.domain 兜底一次（个别号 domain 是 copilot.tencent.com）。
GROWTH_HOSTS = ["https://www.workbuddy.cn", "https://www.codebuddy.cn"]


def growth_api(cred, path, method="GET", body=None):
    """请求成长中心接口（/activity/growth/*，无 /v2 前缀），主机逐个兜底。

    端点来源：成长中心前端 bundle（growthSpace 模块）实测提取 ——
      GET  /activity/growth/energy          能量余额
      GET  /activity/growth/buddy/quota     盲盒配额（cost_per_open / affordable）
      POST /activity/growth/buddy/open      开盲盒
      GET  /activity/growth/buddy/travel/status   旅行状态
      POST /activity/growth/buddy/travel/claim    领到达奖励
      POST /activity/growth/buddy/travel/depart   派猫猫（body: location_id）
    """
    auth = cred.get("auth") or {}
    token = auth.get("accessToken")
    if not token:
        raise ValueError("凭证里没有 accessToken")
    hosts = list(GROWTH_HOSTS) + ["https://" + str(auth.get("domain") or "www.workbuddy.cn")]
    last = ""
    for host in hosts:
        url = host + path
        payload = json.dumps(body if body is not None else {}).encode() if method == "POST" else None
        try:
            req = urllib.request.Request(url, method=method, data=payload)
            req.add_header("Authorization", "Bearer " + token)
            req.add_header("Content-Type", "application/json")
            req.add_header("x-codebuddy-request", "1")
            req.add_header("x-client-platform", "web")
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as e:
            last = "%s(%s)" % (type(e).__name__, str(e)[:80])
    raise RuntimeError("成长接口全部主机失败：%s" % last)


def task_buddy_blindbox(cred, account=None, check_only=False):
    """开启盲盒：能量够就开，能量不够如实跳过（绝不硬开、绝不循环开到爆）。"""
    try:
        q = growth_api(cred, "/activity/growth/buddy/quota")
        d = (q or {}).get("data") or {}
        cost = int(d.get("cost_per_open") or 0)
        bal = int(d.get("balance") or 0)
        affordable = int(d.get("affordable") or 0)
        max_open = int(d.get("max_open_count") or 1)
        if check_only:
            return {"status": STATUS_OK, "code": "quota", "data": d,
                    "reason": "能量 %d，单次消耗 %d，当前可开 %d 次" % (bal, cost, affordable)}
        if affordable <= 0:
            return {"status": STATUS_OK, "code": "not_enough_energy", "data": d,
                    "reason": "能量不足（%d/%d），本次不开盲盒" % (bal, cost)}
        opened = []
        for _ in range(min(affordable, max_open)):
            r = growth_api(cred, "/activity/growth/buddy/open", "POST", {})
            od = (r or {}).get("data") or {}
            opened.append({"name": (od.get("buddy") or {}).get("name") or od.get("name"),
                           "rarity": (od.get("buddy") or {}).get("rarity") or od.get("rarity"),
                           "code": r.get("code")})
            if (r or {}).get("code") not in (0, None):
                break
        return {"status": STATUS_OK, "code": "opened", "data": {"opened": opened},
                "reason": "开启盲盒 %d 次（消耗 %d 能量）" % (len(opened), cost * len(opened))}
    except Exception as e:
        return {"status": STATUS_FAIL, "code": "exception", "reason": "%s: %s" % (type(e).__name__, str(e)[:160])}


def task_buddy_travel_dispatch(cred, account=None, check_only=False):
    """派猫猫旅行：先领已到达奖励，再在「空闲且未达每日上限」时派出（先领后派）。"""
    def _status():
        r = growth_api(cred, "/activity/growth/buddy/travel/status")
        return (r or {}).get("data") or {}

    try:
        d = _status()
        state = d.get("state")
        notes = []
        # 1) 已到达 → 先领积分（不领不会丢，但能领就领）
        if state == "arrived":
            if check_only:
                notes.append("已到达待领取（本次只查询未领取）")
            else:
                cr = growth_api(cred, "/activity/growth/buddy/travel/claim", "POST", {})
                notes.append("领取到达奖励（code=%s）" % (cr or {}).get("code"))
                d = _status()
                state = d.get("state")
        # 2) 空闲 → 派出（每日上限内）
        if state == "idle":
            if d.get("daily_limit_reached"):
                notes.append("今日派遣已达上限，跳过")
            elif check_only:
                notes.append("空闲可派（本次只查询未派遣）")
            else:
                import random
                loc = int(os.environ.get("WB_TRAVEL_LOCATION") or random.randint(1, 4))
                dr = growth_api(cred, "/activity/growth/buddy/travel/depart", "POST",
                                {"location_id": loc})
                notes.append("已派往地点 %d（code=%s）" % (loc, (dr or {}).get("code")))
                d = _status()
        elif state == "traveling":
            notes.append("旅行中，等待到达（无召回接口）")
        return {"status": STATUS_OK, "code": state or "unknown", "data": d,
                "reason": "；".join(notes) or "状态 %s" % state}
    except Exception as e:
        return {"status": STATUS_FAIL, "code": "exception", "reason": "%s: %s" % (type(e).__name__, str(e)[:160])}


TASKS = {
    "checkin": ("每日签到", task_checkin),
    "growth_tasks": ("成长任务清单", task_growth_tasks),
    "growth_info": ("成长伙伴状态", task_growth_info),
    "growth_travel_claim": ("出行到达奖励", task_growth_travel_claim),
    "growth_active": ("成长热度点亮", task_growth_active),
    "buddy_blindbox": ("开启盲盒", task_buddy_blindbox),
    "buddy_travel_dispatch": ("派猫猫旅行", task_buddy_travel_dispatch),
}

# 账号配置里应当存在的任务开关（缺了按默认补全，保证新老配置都能跑）
DEFAULT_TASKS = {k: True for k in TASKS}


# --------------------------------------------------------------------------- #
# 调度判定
# --------------------------------------------------------------------------- #
def is_due(account, cfg, force=False):
    """判断该账号当前是否到点（计划任务触发时刻 ± window_minutes）。"""
    if force:
        return True, "force"
    if cfg["schedule"].get("trigger_mode", "daily") == "interval":
        return True, "interval"
    window = int(cfg["schedule"].get("window_minutes", 25))
    now = datetime.now()
    for t in account.get("times", []):
        try:
            hh, mm = [int(x) for x in t.split(":")]
        except Exception:
            continue
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if abs((now - target).total_seconds()) <= window * 60:
            return True, t
    return False, ""


def run_account(account, cfg, check_only=False):
    cred, err = load_cred(account)
    label = f"{account.get('label') or account['key']}({account['key']})"
    if err:
        return {"account": account["key"], "label": account.get("label", ""),
                "nickname": account.get("nickname", ""), "status": STATUS_FAIL,
                "tasks": {}, "reason": err}

    exp = cred_expiry_days(cred)
    results = {}
    for name, enabled in (account.get("tasks") or {}).items():
        if not enabled or name not in TASKS:
            continue
        fn = TASKS[name][1]
        try:
            results[name] = fn(cred, account=account, check_only=check_only)
        except Exception as e:
            results[name] = {"status": STATUS_FAIL, "code": "exception", "reason": f"{type(e).__name__}: {e}"}

    failed = [k for k, v in results.items() if v["status"] == STATUS_FAIL]
    overall = STATUS_FAIL if failed else STATUS_OK
    summary = "；".join(f"{TASKS[k][0]}:{v['reason']}" for k, v in results.items())
    return {
        "account": account["key"], "label": account.get("label", ""),
        "nickname": (cred.get("account") or {}).get("nickname", ""),
        "status": overall, "tasks": results, "reason": summary,
        "cred_expiry_days": round(exp, 1) if exp is not None else None,
    }


# --------------------------------------------------------------------------- #
# 计划任务
# --------------------------------------------------------------------------- #
def scheduler_command(cfg):
    py = cfg.get("python_path") or sys.executable
    script = os.path.join(BASE_DIR, "auto_buddy.py")
    return f'cmd /c cd /d "{BASE_DIR}" && "{py}" "{script}" --run >> "{os.path.join(LOG_DIR, "scheduler.log")}" 2>&1'


def install_scheduler(cfg):
    sch = cfg.get("schedule", {})
    mode = sch.get("trigger_mode", "daily")
    prefix = sch.get("task_prefix", "WorkBuddyAuto")
    cmd = scheduler_command(cfg)
    os.makedirs(LOG_DIR, exist_ok=True)

    specs = []
    if mode == "interval":
        every = max(30, int(sch.get("every_minutes", 60)))
        specs.append((f"{prefix}_Interval", f"/SC MINUTE /MO {every}"))
    else:
        times = []
        for a in cfg["accounts"]:
            if not a.get("enabled", True):
                continue
            for t in a.get("times", []):
                if t not in times:
                    times.append(t)
        times.sort()
        for t in times:
            specs.append((f"{prefix}_{t.replace(':', '')}", f"/SC DAILY /ST {t}"))

    ok = True
    for name, trigger in specs:
        r = subprocess.run(
            f'schtasks /Create /TN "{name}" /TR "{cmd}" {trigger} /F',
            shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if r.returncode == 0:
            print(f"[已注册] {name}  {trigger}")
        else:
            ok = False
            print(f"[失败] {name}: {r.stderr.strip() or r.stdout.strip()}")
    if ok:
        print(f"共 {len(specs)} 个定时任务，执行内容：{cmd}")
    return 0 if ok else 1


def remove_scheduler(cfg):
    prefix = cfg.get("schedule", {}).get("task_prefix", "WorkBuddyAuto")
    r = subprocess.run("schtasks /Query /FO CSV", shell=True, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    names = [line.split(",")[0].strip('"') for line in r.stdout.splitlines()
             if line.startswith('"') and line.split(",")[0].strip('"').startswith(prefix)]
    for n in names:
        subprocess.run(f'schtasks /Delete /TN "{n}" /F', shell=True,
                       capture_output=True, text=True)
        print(f"[已删除] {n}")
    print(f"共删除 {len(names)} 个")
    return 0


# --------------------------------------------------------------------------- #
# 命令
# --------------------------------------------------------------------------- #
def cmd_discover(cfg):
    print("本机保存过的登录态（按最近使用排序）：")
    print("-" * 96)
    print(f"{'昵称':<28}{'UID':<38}{'手机':<13}{'保存时间':<21}{'剩余天数':>8}")
    print("-" * 96)
    for a in discover_accounts():
        print(f"{a['nickname'][:26]:<28}{a['uid']:<38}{a['phone']:<13}{a['saved_at']:<21}{a['expiry_days']:>8}")
    print("-" * 96)
    print("用法：客户端登录目标账号 -> python auto_buddy.py --capture <key>")
    return 0


def cmd_list(cfg):
    runs = []
    if os.path.exists(RUNS_LOG):
        with open(RUNS_LOG, encoding="utf-8") as f:
            runs = [json.loads(l) for l in f if l.strip()]
    print(f"{'账号':<12}{'备注':<14}{'状态':<8}{'凭证剩余':<10}最近执行")
    print("-" * 92)
    for a in cfg["accounts"]:
        last = next((r for r in reversed(runs) if r.get("account") == a["key"]), None)
        cred, err = load_cred(a)
        exp = f"{cred_expiry_days(cred):.0f}天" if cred else "缺失"
        state = "停用" if not a.get("enabled", True) else ("正常" if cred else "凭证失效")
        stamp = f"{last['ts']} | {last.get('reason','')[:44]}" if last else "从未执行"
        print(f"{a['key']:<12}{a.get('label',''):<14}{state:<8}{exp:<10}{stamp}")
    return 0


def cmd_run(cfg, args):
    due = []
    for a in cfg["accounts"]:
        if not a.get("enabled", True):
            continue
        if args.account and args.account not in (a["key"], a.get("label")):
            continue
        ok, why = is_due(a, cfg, force=args.force)
        if ok:
            due.append((a, why))
        elif args.account:
            print(f"[跳过] {a['key']} 未到点（配置为 {','.join(a.get('times', []))}，当前 {now_str()}）")

    if not due:
        print(f"[{now_str()}] 没有到点的账号，本次不执行（加 --force 可强制执行）")
        return 0

    print(f"===== 执行开始 {now_str()} | 账号数 {len(due)} | {'仅查询' if args.check else '正式执行'} =====")
    all_results, has_fail, has_auth_fail = [], False, False
    for a, why in due:
        try:
            res = run_account(a, cfg, check_only=args.check)
        except Exception as e:          # 单个账号异常不能中断整体流程
            res = {"account": a["key"], "label": a.get("label", ""), "status": STATUS_FAIL,
                   "tasks": {}, "reason": f"账号级异常：{type(e).__name__}: {e}"}
        res["ts"] = now_str()
        res["trigger"] = why
        res["date"] = today_str()
        all_results.append(res)
        append_run(res)
        flag = {"success": "成功", "skip": "跳过", "fail": "失败"}[res["status"]]
        print(f"\n[{flag}] {res['label']} {res.get('nickname','')}  (触发:{why})")
        for k, v in res.get("tasks", {}).items():
            mark = {"success": "成功", "skip": "跳过", "fail": "失败"}[v["status"]]
            print(f"    - {TASKS[k][0]}: [{mark}] {v['reason']}")
            if v.get("steps"):
                for s in v["steps"]:
                    if s.get("step") in ("skip",):
                        continue
                    print(f"        · {s.get('title') or s.get('task')} "
                          f"[{s['step']}/{s['status']}] {s['reason']}")

        # 单账号积分余额（执行前 → 执行后 → 增量），拿不到就明确报错
        gt = (res.get("tasks") or {}).get("growth_tasks") or {}
        b0, b1, bd = gt.get("balance_before"), gt.get("balance_after"), gt.get("balance_delta")
        if gt.get("balance_error") or b1 is None:
            print(f"    ! 积分余额获取失败：{gt.get('balance_error') or '接口未返回余额'}")
        else:
            sign = "+" if (bd or 0) >= 0 else ""
            print(f"    · 积分余额：{b0} → {b1}（增量 {sign}{bd}）"
                  + (f"；本次任务领取 +{gt.get('credit_got')} 积分" if gt.get("credit_got") else ""))
        res["balance"] = {"before": b0, "after": b1, "delta": bd,
                          "error": gt.get("balance_error", ""), "credit_got": gt.get("credit_got", 0)}
        if res["status"] == STATUS_FAIL:
            has_fail = True
            if any(v.get("code") == "auth_expired" for v in res["tasks"].values()):
                has_auth_fail = True
        if res.get("cred_expiry_days") is not None and res["cred_expiry_days"] < 7:
            notify("凭证即将过期",
                   f"{res['label']} 的登录凭证 {res['cred_expiry_days']:.0f} 天后过期，"
                   f"请登录客户端后执行 --capture {res['account']}")
            print(f"    ! 凭证 {res['cred_expiry_days']:.0f} 天后过期，请尽快重新抓取")

    save_json(LATEST_JSON, {"ts": now_str(), "results": all_results})

    # ---------- 汇总：每个账号的积分变化 + 任务完成 / 跳过 / 失败 ----------
    lines = [f"===== {now_str()} 积分汇总（账号标识 / 执行前 / 执行后 / 增量） ====="]
    print("\n" + lines[0])
    for r in all_results:
        b = r.get("balance") or {}
        b0, b1, bd = b.get("before"), b.get("after"), b.get("delta")
        ident = f"{r['account']}({r.get('label') or ''})"
        if b.get("error") or b1 is None:
            lines.append(f"[余额获取失败] {ident}：{b.get('error') or '接口未返回余额'}")
            print(f"  {ident:<26} 余额获取失败：{b.get('error') or '接口未返回余额'}")
        else:
            sign = "+" if (bd or 0) >= 0 else ""
            line = f"{ident}  {b0} → {b1}  ({sign}{bd})"
            lines.append(line)
            print(f"  {ident:<26} {str(b0):>6} → {str(b1):>6}  ({sign}{bd})")

    note = ("说明：积分余额 = Buddy加油站积分（官方唯一暴露的余额口径）；"
            "成长任务领取的积分计入成长账户、无公开余额接口，"
            "所以「增量」只反映签到变化，任务获得的积分在每个账号下单独列出。")
    lines.append(note)
    print("  " + note)

    lines.append("")
    lines.append(f"===== {now_str()} 任务明细（完成 / 跳过 / 失败） =====")
    print("\n" + lines[-1])
    for r in all_results:
        gt = (r.get("tasks") or {}).get("growth_tasks") or {}
        s = gt.get("summary") or {}
        print(f"\n  账号 {r['account']}（{r.get('label') or ''}）"
              f"  完成 {s.get('done', '-')}/{s.get('total', '-')}"
              f"  领取 {s.get('claimed', 0)}  接取 {s.get('accepted', 0)}"
              f"  跳过付费 {s.get('skipped_paid', 0)}  跳过其它 {s.get('skipped_other', 0)}"
              f"  失败 {s.get('failed', 0)}")
        lines.append(f"账号 {r['account']}：完成 {s.get('done','-')}/{s.get('total','-')}，"
                     f"领取 {s.get('claimed',0)}，跳过付费 {s.get('skipped_paid',0)}，失败 {s.get('failed',0)}")
        for p in gt.get("skipped_paid", []):
            print(f"      [跳过·需付费] {p['title']}（{p['task']}）：{p['reason']}")
            lines.append(f"    跳过付费：{p['title']} —— {p['reason']}")
        for f in gt.get("failed_tasks", []):
            print(f"      [失败] {f['title']}（{f['task']}）：{f['reason']}")
            lines.append(f"    失败：{f['title']} —— {f['reason']}")
        if r["status"] == STATUS_FAIL:
            print(f"      [账号失败] {r.get('reason','')}")
            lines.append(f"    账号失败：{r.get('reason','')}")

    os.makedirs(LOG_DIR, exist_ok=True)
    with open(SUMMARY_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    alert_cfg = cfg.get("alert", {})
    if has_fail:
        failed_names = "、".join(r["label"] for r in all_results if r["status"] == STATUS_FAIL)
        detail = " | ".join(r.get("reason", "")[:80] for r in all_results if r["status"] == STATUS_FAIL)
        print(f"\n[告警] 以下账号执行失败：{failed_names}")
        notify("Buddy 自动任务失败", f"{failed_names}：{detail}")
    elif alert_cfg.get("notify_on_success"):
        notify("Buddy 自动任务完成", "\n".join(f"{r['label']}: {r.get('reason','')[:60]}" for r in all_results))
    if has_auth_fail:
        print("[处理建议] 有账号登录态失效：打开 WorkBuddy 客户端登录对应微信号，"
              "然后执行 python auto_buddy.py --capture <key>")

    return 2 if has_auth_fail else (1 if has_fail else 0)


def main():
    parser = argparse.ArgumentParser(description="WorkBuddy 双账号自动签到 / 成长计划任务")
    parser.add_argument("--discover", action="store_true", help="扫描本机所有可用登录态")
    parser.add_argument("--capture", metavar="KEY", help="把客户端当前登录账号存为 KEY 的凭证")
    parser.add_argument("--from-file", metavar="PATH", help="配合 --capture：从指定登录态文件抓取")
    parser.add_argument("--allow-mismatch", action="store_true", help="capture 时允许 UID 不一致")
    parser.add_argument("--list", action="store_true", help="列出配置账号与最近状态")
    parser.add_argument("--sync", action="store_true", help="扫描本机登录态，新账号自动入库")
    parser.add_argument("--run", action="store_true", help="执行到点账号")
    parser.add_argument("--check", action="store_true", help="配合 --run：只查询不领取")
    parser.add_argument("--account", metavar="KEY", help="只处理指定账号")
    parser.add_argument("--force", action="store_true", help="忽略时间窗强制执行")
    parser.add_argument("--install-scheduler", action="store_true", help="注册 Windows 计划任务")
    parser.add_argument("--remove-scheduler", action="store_true", help="删除计划任务")
    parser.add_argument("--add", metavar="UID", help="把本机某个登录态账号加入配置列表")
    parser.add_argument("--remove", metavar="KEY", help="从配置列表移除账号")
    parser.add_argument("--enable", metavar="KEY", help="启用账号")
    parser.add_argument("--disable", metavar="KEY", help="停用账号")
    parser.add_argument("--capture-all", action="store_true", help="一键续期所有账号凭证")
    parser.add_argument("--ui", action="store_true", help="启动本地网页管理界面")
    parser.add_argument("--port", type=int, default=8765, help="网页界面端口，默认 8765")
    parser.add_argument("--notify-test", action="store_true", help="测试提醒通道")
    args = parser.parse_args()

    cfg = load_config()

    if args.discover:
        return cmd_discover(cfg)
    if args.capture:
        acc = next((a for a in cfg["accounts"] if a["key"] == args.capture), None)
        if not acc:
            print(f"[失败] 配置里没有 key={args.capture} 的账号，先在 config.json 里加一个。")
            return 1
        rc, msg = capture(acc, allow_mismatch=args.allow_mismatch, source=args.from_file)
        print(("[成功] " if rc == 0 else "[失败] ") + msg)
        return rc
    if args.list:
        return cmd_list(cfg)
    if args.install_scheduler:
        return install_scheduler(cfg)
    if args.remove_scheduler:
        return remove_scheduler(cfg)
    if args.capture_all:
        ok, skipped = capture_all_possible()
        print(f"[完成] 已续期 {len(ok)} 个：{', '.join(ok) or '无'}")
        if skipped:
            print("[需手动登录] " + "；".join(skipped))
            print("           打开客户端扫码登录后，再执行一次本命令即可")
        return 0 if not skipped else 1
    if args.add:
        acc, msg = add_account_by_uid(args.add)
        print(("[成功] " if acc else "[失败] ") + msg)
        return 0 if acc else 1
    if args.remove:
        ok, msg = remove_account(args.remove)
        print(("[成功] " if ok else "[失败] ") + msg)
        return 0 if ok else 1
    if args.enable:
        ok, msg = set_enabled(args.enable, True)
        print(("[成功] " if ok else "[失败] ") + msg)
        return 0 if ok else 1
    if args.disable:
        ok, msg = set_enabled(args.disable, False)
        print(("[成功] " if ok else "[失败] ") + msg)
        return 0 if ok else 1
    if args.ui:
        try:
            import server
        except Exception as e:
            print(f"[失败] 无法加载网页界面模块：{e}")
            return 1
        return server.serve(args.port)
    if args.notify_test:
        notify("Buddy 提醒测试", "如果你看到这条气泡，说明告警通道正常。")
        print("已发送测试提醒。")
        return 0
    if args.sync:
        added, skipped = auto_sync_accounts()
        print(f"[自动入库] 新增 {len(added)} 个账号"
              + (f"：{'、'.join(a['label'] for a in added)}" if added else ""))
        for s in skipped:
            print(f"           跳过 {s}")
    if args.run:
        return cmd_run(cfg, args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
