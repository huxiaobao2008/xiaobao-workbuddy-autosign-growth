#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成长计划任务引擎（签到之外的「成长任务」自动执行）

沿用 auto_buddy.py 的凭证、接口调用与日志体系，只负责：
  拉取任务列表 -> 判定状态 -> 串行接取/领取 -> 回写最新状态 -> 结构化日志

真实接口（已从官网 usercenter 前端产物 + 本机 app.asar 双向核实，非猜测）：
  GET  /v2/activity/growth/tasks              成长任务列表
  POST /activity/growth/tasks/accept          接取任务   body: {task_codes:[...]}
  POST /activity/growth/tasks/{code}/claim    领取奖励
  GET  /v2/activity/growth/profile            成长档案（等级/已完成/任务总数）

任务 accept_status 取值（前端枚举）：
  not_accepted 未接取 | accepted 已接取 | in_progress 进行中 | completed 待领取 | claimed 已领取

设计约束：
- 全程串行：模块级 SERIAL_LOCK，任何时刻只允许一个账号在执行，并发请求直接返回「执行中」
- 单任务失败不影响其它任务：每个任务独立 try/except，失败只记录
- 不重复提交：已领取/已过期/已锁定一律跳过；claim 返回 already_claimed 视为跳过而非失败
- 失败重试：仅对网络异常与 5xx 重试，业务错误（4xx 带 msg）不重试
"""
import json
import os
import re
import threading
import time
from datetime import datetime

import auto_buddy as core

BASE_DIR = core.BASE_DIR
LOG_DIR = core.LOG_DIR
TASK_LOG = os.path.join(LOG_DIR, "tasks.jsonl")
TASK_STATE = os.path.join(LOG_DIR, "tasks_state.json")

PATH_TASKS = "/v2/activity/growth/tasks"
PATH_ACCEPT = "/activity/growth/tasks/accept"
PATH_CLAIM = "/activity/growth/tasks/{code}/claim"
PATH_PROFILE = "/v2/activity/growth/profile"

# 串行执行锁（CLI / 网页 / 定时任务共用）
SERIAL_LOCK = threading.Lock()

STATUS_LABEL = {
    "not_accepted": "未接取",
    "accepted": "已接取",
    "in_progress": "进行中",
    "completed": "待领取",
    "claimed": "已领取",
}

# 领取接口返回这些 msg 表示「当前不该领」，按跳过处理，不算失败
BENIGN_CLAIM_MSG = ("not completed", "already", "claimed", "not arrived", "expired", "locked")

# 需要花钱/捐款才能完成的任务：命中后一律跳过，绝不执行、绝不产生扣费
DEFAULT_PAID_CODES = ["Expert_Philanthropy"]          # 显式名单：体验「公益专家」（需完成1次捐款）
DEFAULT_PAID_KEYWORDS = ["捐款", "捐赠", "捐助", "献爱心", "公益", "付费", "充值",
                         "支付", "购买", "消费", "下单", "开通会员", "¥"]


def paid_rule(cfg):
    """付费任务判定规则：配置文件可覆盖。"""
    cfg = cfg or {}
    block = cfg.get("paid_tasks") or {}
    codes = [c.lower() for c in (block.get("codes") or DEFAULT_PAID_CODES)]
    keywords = list(block.get("keywords") or DEFAULT_PAID_KEYWORDS)
    return codes, keywords


def detect_paid(raw, cfg=None):
    """返回 (是否付费任务, 判定原因)。规则：显式名单 > 文案关键词。"""
    codes, keywords = paid_rule(cfg)
    code = (raw.get("task_code") or "").lower()
    if code in codes:
        return True, f"命中付费任务名单（{raw.get('task_code')}）"
    text = " ".join(str(raw.get(k) or "") for k in ("title", "task_desc", "description", "badge_name"))
    for kw in keywords:
        if kw in text:
            return True, f"任务文案含「{kw}」，判定为需付费/捐款"
    return False, ""


# 「用户明确要求不执行」的任务：连接取/领取都不做，进度也不动。
# 与 paid_tasks 的区别：付费任务是为了不花钱；这里纯粹是用户不想刷（例如
# black_cat 夜猫子要连续 3 个晚上、奖励还是 Buddy 不是积分）。
# 用配置而不是硬编码，改 config.json 即可恢复。
DEFAULT_SKIP_CODES = ["black_cat"]
DEFAULT_SKIP_KEYWORDS = []


def skip_rule(cfg):
    """不执行任务的判定规则：配置文件可覆盖。"""
    cfg = cfg or {}
    block = cfg.get("skip_tasks") or {}
    codes = [c.lower() for c in (block.get("codes") or DEFAULT_SKIP_CODES)]
    keywords = list(block.get("keywords") or DEFAULT_SKIP_KEYWORDS)
    return codes, keywords


def detect_skip(raw, cfg=None):
    """返回 (是否按要求不执行, 原因)。"""
    codes, keywords = skip_rule(cfg)
    code = (raw.get("task_code") or "").lower()
    if code in codes:
        return True, "按用户要求不执行该任务"
    text = " ".join(str(raw.get(k) or "") for k in ("title", "task_desc", "description", "badge_name"))
    for kw in keywords:
        if kw and kw in text:
            return True, f"任务文案含「{kw}」，按用户要求不执行"
    return False, ""


# --------------------------------------------------------------------------- #
# 结构化日志
# --------------------------------------------------------------------------- #
def log_step(account_key, nickname, task_code, task_title, step, status, reason, extra=None):
    rec = {
        "ts": core.now_str(), "date": core.today_str(),
        "account": account_key, "nickname": nickname,
        "task": task_code, "task_title": task_title, "step": step,
        "status": status, "reason": reason,
    }
    if extra:
        rec["extra"] = extra
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(TASK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def save_state(state):
    """回写最新任务快照，保证页面展示与真实执行结果一致。"""
    os.makedirs(LOG_DIR, exist_ok=True)
    core.save_json(TASK_STATE, {"ts": core.now_str(), "accounts": state})


# --------------------------------------------------------------------------- #
# 接口调用（带重试）
# --------------------------------------------------------------------------- #
def _retry(fn, attempts=2, backoff=2):
    """网络异常(-1)与 5xx 才重试；业务错误直接返回。"""
    last = (-1, {"error": "未执行"})
    for i in range(max(1, attempts)):
        code, res = fn()
        retryable = (code == -1) or (isinstance(code, int) and code >= 500)
        if not retryable:
            return code, res
        last = (code, res)
        if i < attempts - 1:
            time.sleep(backoff * (i + 1))
    return last


def api_tasks(cred, cfg=None):
    attempts = int((cfg or {}).get("retry", {}).get("attempts", 2))
    backoff = int((cfg or {}).get("retry", {}).get("backoff_seconds", 2))
    return _retry(lambda: core.api(cred, PATH_TASKS, method="GET"), attempts, backoff)


def api_profile(cred, cfg=None):
    return core.api(cred, PATH_PROFILE, method="GET")


# --------------------------------------------------------------------------- #
# 状态判定
# --------------------------------------------------------------------------- #
def _expired(valid_end):
    if not valid_end:
        return False
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(valid_end)[:19], fmt) < datetime.now()
        except Exception:
            continue
    return False


def normalize(raw, cfg=None):
    """把接口原始任务对象整理成前后端共用的结构（页面与执行结果以这一份为准）。"""
    prog = raw.get("progress") or {}
    cur, tgt = prog.get("current"), prog.get("target")
    status = raw.get("accept_status") or "not_accepted"
    expired = _expired(raw.get("valid_end"))
    locked = bool(raw.get("locked"))
    paid, paid_reason = detect_paid(raw, cfg)
    skip, skip_reason = detect_skip(raw, cfg)
    progress_done = bool(tgt and cur is not None and cur >= tgt)
    # 付费任务一票否决：既不接取也不领取
    # 不执行任务同理：用户说了不刷，就别接、别领、别推动进度
    claimable = (not locked) and (not expired) and (not paid) and (not skip) and status != "claimed" and (
        status == "completed" or progress_done
    )
    item = {
        "code": raw.get("task_code"),
        "title": raw.get("title") or raw.get("task_code"),
        "desc": raw.get("task_desc") or raw.get("description") or "",
        "status": status,
        "status_label": STATUS_LABEL.get(status, status),
        "done": status == "claimed",                      # 已完成（已领取）
        "progress": {"current": cur, "target": tgt},
        "progress_text": f"{cur}/{tgt}" if (cur is not None and tgt) else "—",
        "reward_credit": raw.get("reward_credit") or 0,   # 可得积分
        "reward_energy": raw.get("reward_energy") or 0,
        "locked": locked,
        "expired": expired,
        "valid_end": raw.get("valid_end"),
        "claimable": claimable,
        "accept_needed": status == "not_accepted" and not paid and not skip,
        "paid": paid,
        "paid_reason": paid_reason,
        "skip": skip,
        "skip_reason": skip_reason,
        "jump_url": raw.get("jump_url") or "",
    }
    if paid:
        item["status_label"] = "已跳过（需付费）"
    elif skip:
        item["status_label"] = "已跳过（按要求不执行）"
    return item


def summarize(tasks):
    done = [t for t in tasks if t["done"]]
    undone = [t for t in tasks if not t["done"]]
    return {
        "total": len(tasks),
        "done": len(done),
        "undone": len(undone),
        "paid_skipped": sum(1 for t in tasks if t.get("paid") and not t["done"]),
        # 真正能领的：已完成且服务端允许领取的任务积分
        "pending_credit": sum(t["reward_credit"] for t in tasks if t.get("claimable")),
        # 只是「做完才能拿」的潜在积分，不是待领，别混为一谈
        "potential_credit": sum(t["reward_credit"] for t in undone
                                if not t["locked"] and not t["expired"] and not t.get("paid")),
        "claimable": sum(1 for t in tasks if t["claimable"]),
    }


def fetch_tasks(cred, cfg=None):
    """返回 (tasks_normalized, err)。err 非空表示拉取失败。"""
    code, res = api_tasks(cred, cfg)
    if core.auth_error(code, res):
        return [], "登录态失效（401/403）"
    if code != 200 or res.get("code") != 0:
        return [], f"任务列表拉取失败 http={code} biz={res.get('code')} msg={res.get('msg','')}"
    raw = ((res.get("data") or {}).get("tasks")) or []
    return [normalize(t, cfg) for t in raw], ""


def fetch_profile(cred, cfg=None):
    code, res = api_profile(cred, cfg)
    if code != 200 or res.get("code") != 0:
        return {}, f"成长档案拉取失败 http={code} biz={res.get('code')}"
    d = res.get("data") or {}
    return {"level": d.get("level"), "completed": d.get("completed"), "total": d.get("total")}, ""


# --------------------------------------------------------------------------- #
# 单个任务动作
# --------------------------------------------------------------------------- #
def accept_task(cred, code, cfg=None):
    attempts = int((cfg or {}).get("retry", {}).get("attempts", 2))
    backoff = int((cfg or {}).get("retry", {}).get("backoff_seconds", 2))
    c, r = _retry(lambda: core.api(cred, PATH_ACCEPT, method="POST", body={"task_codes": [code]}),
                  attempts, backoff)
    if core.auth_error(c, r):
        return False, "登录态失效（401/403）", "auth_expired"
    if c != 200 or r.get("code") != 0:
        return False, f"接取失败 http={c} biz={r.get('code')} msg={r.get('msg','')}", "api_error"
    results = ((r.get("data") or {}).get("results")) or []
    st = results[0].get("status") if results else "accepted"
    return True, f"已接取（{st}）", "accepted"


def claim_task(cred, code, cfg=None):
    attempts = int((cfg or {}).get("retry", {}).get("attempts", 2))
    backoff = int((cfg or {}).get("retry", {}).get("backoff_seconds", 2))
    c, r = _retry(lambda: core.api(cred, PATH_CLAIM.format(code=code), method="POST"),
                  attempts, backoff)
    if core.auth_error(c, r):
        return False, "登录态失效（401/403）", "auth_expired"
    if c != 200 or r.get("code") != 0:
        msg = (r.get("msg") or "").lower()
        if any(k in msg for k in BENIGN_CLAIM_MSG):
            return None, f"跳过：{r.get('msg')}", "no_pending"
        return False, f"领取失败 http={c} biz={r.get('code')} msg={r.get('msg','')}", "api_error"
    d = r.get("data") or {}
    if d.get("already_claimed"):
        return None, "跳过：已领取过", "already_claimed"
    return True, f"领取成功 +{d.get('credit', 0)} 积分", "claimed"


# --------------------------------------------------------------------------- #
# 串行执行
# --------------------------------------------------------------------------- #
def run_tasks(cred, account, cfg=None, do_accept=True, do_claim=True):
    """
    串行执行一个账号的成长任务。返回 dict：
      {status, reason, steps:[...], tasks:[最新状态], summary:{...}, profile:{...}}
    status: success / skip / fail
    """
    key = account["key"]
    nick = account.get("nickname") or account.get("label") or key
    steps = []
    skipped_paid, skipped_other, failed_list = [], [], []

    # 执行前积分余额（积分余额口径：签到接口的 total_credits）
    bal_before = core.query_credits(cred)
    before_val = bal_before.get("total_credits")
    if bal_before.get("err") or before_val is None:
        log_step(key, nick, "-", "-", "balance", "fail", f"执行前积分余额获取失败：{bal_before.get('err') or '返回为空'}")

    tasks, err = fetch_tasks(cred, cfg)
    if err:
        log_step(key, nick, "-", "-", "fetch", "fail", err)
        return {"status": "fail", "reason": err, "steps": [
            {"task": "-", "step": "fetch", "status": "fail", "reason": err}],
            "tasks": [], "summary": {}, "profile": {},
            "balance_before": before_val, "balance_after": None, "balance_delta": None,
            "balance_error": bal_before.get("err") or ("执行前余额获取失败" if before_val is None else ""),
            "credit_got": 0, "skipped_paid": [], "skipped_other": [], "failed_tasks": []}

    profile, perr = fetch_profile(cred, cfg)

    claimed_cnt = credit_got = accepted_cnt = 0
    failed = 0
    for t in tasks:
        code_, title = t["code"], t["title"]
        try:
            # 0) 付费/捐款任务：一票否决，不接取、不领取、不产生任何扣费
            if t.get("paid"):
                reason = f"已跳过（需付费）：{t.get('paid_reason')}"
                steps.append({"task": code_, "title": title, "step": "skip_paid",
                              "status": "skip", "reason": reason})
                log_step(key, nick, code_, title, "skip_paid", "skip", reason)
                skipped_paid.append({"task": code_, "title": title, "reason": reason})
                continue
            if t.get("skip"):
                reason = "按用户要求不执行：%s" % (t.get("skip_reason") or "")
                steps.append({"task": code_, "title": title, "step": "skip_required",
                              "status": "skip", "reason": reason})
                log_step(key, nick, code_, title, "skip_required", "skip", reason)
                skipped_other.append({"task": code_, "title": title, "reason": reason})
                continue
            if t["locked"]:
                steps.append({"task": code_, "title": title, "step": "skip",
                              "status": "skip", "reason": "任务已锁定"})
                log_step(key, nick, code_, title, "skip", "skip", "任务已锁定")
                skipped_other.append({"task": code_, "title": title, "reason": "任务已锁定"})
                continue
            if t["expired"]:
                reason = f"已过期（截止 {t['valid_end']}）"
                steps.append({"task": code_, "title": title, "step": "skip",
                              "status": "skip", "reason": reason})
                log_step(key, nick, code_, title, "skip", "skip", reason)
                skipped_other.append({"task": code_, "title": title, "reason": reason})
                continue
            if t["done"]:
                steps.append({"task": code_, "title": title, "step": "skip",
                              "status": "skip", "reason": "已领取，不重复提交"})
                log_step(key, nick, code_, title, "skip", "skip", "已领取")
                continue

            # 1) 未接取 -> 先接取
            status_now = t["status"]
            if do_accept and t["accept_needed"]:
                ok, msg, code2 = accept_task(cred, code_, cfg)
                steps.append({"task": code_, "title": title, "step": "accept",
                              "status": "success" if ok else ("fail" if ok is False else "skip"), "reason": msg})
                log_step(key, nick, code_, title, "accept",
                         "success" if ok else ("fail" if ok is False else "skip"), msg)
                if ok is False:
                    failed += 1
                    failed_list.append({"task": code_, "title": title, "reason": msg})
                    continue
                if ok:
                    accepted_cnt += 1
                    status_now = "accepted"
                    # 接取后服务端进度可能立即刷新；t 还是接取前的旧快照，
                    # 直接拿它判"是否可领"会把刚完成的任务误判成未完成 → 漏领。
                    # 重拉一次任务列表，用新进度做下面的 claimable 判断。
                    lst2, _err2 = fetch_tasks(cred, cfg)
                    if not _err2:
                        t2 = next((x for x in lst2 if x["code"] == code_), None)
                        if t2:
                            t = t2

            # 2) 进度完成 -> 领取
            claimable = status_now == "completed" or (
                t["progress"]["target"] and (t["progress"]["current"] or 0) >= t["progress"]["target"])
            if do_claim and claimable:
                ok, msg, code2 = claim_task(cred, code_, cfg)
                st = "success" if ok else ("fail" if ok is False else "skip")
                steps.append({"task": code_, "title": title, "step": "claim",
                              "status": st, "reason": msg})
                log_step(key, nick, code_, title, "claim", st, msg)
                if ok:
                    claimed_cnt += 1
                    try:
                        _m = re.search(r"\+\s*(\d+)", msg or "")
                        if _m:
                            credit_got += int(_m.group(1))
                        else:
                            log_step(key, nick, code_, title, "claim", "warn",
                                     "领取成功但无法从文案解析积分：%r" % msg)
                    except Exception:
                        pass
                elif ok is False:
                    failed += 1
                    failed_list.append({"task": code_, "title": title, "reason": msg})
            elif not claimable:
                reason = f"未完成（{t['progress_text']}），需先在客户端完成该操作"
                steps.append({"task": code_, "title": title, "step": "skip", "status": "skip",
                              "reason": reason})
                log_step(key, nick, code_, title, "skip", "skip", reason)
                skipped_other.append({"task": code_, "title": title, "reason": reason})
        except Exception as e:
            reason = f"{type(e).__name__}: {e}"
            steps.append({"task": code_, "title": title, "step": "error", "status": "fail", "reason": reason})
            log_step(key, nick, code_, title, "error", "fail", reason)
            failed += 1
            failed_list.append({"task": code_, "title": title, "reason": reason})
            continue  # 单个任务失败不影响后续

    # 执行完重新拉取，保证回写的是真实最新状态
    fresh, ferr = fetch_tasks(cred, cfg)
    if ferr:
        fresh = tasks

    # 执行后积分余额
    bal_after = core.query_credits(cred)
    after_val = bal_after.get("total_credits")
    balance_error = ""
    if bal_after.get("err") or after_val is None:
        balance_error = f"执行后积分余额获取失败：{bal_after.get('err') or '返回为空'}"
        log_step(key, nick, "-", "-", "balance", "fail", balance_error)
    delta = None
    if before_val is not None and after_val is not None:
        delta = after_val - before_val

    profile2, _ = fetch_profile(cred, cfg)
    if profile2:
        profile = profile2

    summary = summarize(fresh)
    summary.update({"claimed": claimed_cnt, "accepted": accepted_cnt,
                    "credit_got": credit_got, "failed": failed,
                    "skipped_paid": len(skipped_paid), "skipped_other": len(skipped_other)})
    reason = (f"成长任务 {summary['done']}/{summary['total']} 已完成；"
              f"本次接取 {accepted_cnt} 个、领取 {claimed_cnt} 个（+{credit_got} 积分）、"
              f"跳过付费 {len(skipped_paid)} 个"
              + (f"、失败 {failed} 个" if failed else ""))
    return {
        "status": "fail" if failed and claimed_cnt == 0 and accepted_cnt == 0 else "success",
        "reason": reason, "steps": steps, "tasks": fresh,
        "summary": summary, "profile": profile, "profile_error": perr,
        "balance_before": before_val, "balance_after": after_val, "balance_delta": delta,
        "balance_error": balance_error, "credit_got": credit_got,
        "skipped_paid": skipped_paid, "skipped_other": skipped_other, "failed_tasks": failed_list,
    }


def run_account_tasks(account, cfg=None, wait_lock=True):
    """带锁的入口：返回执行结果；拿不到锁时返回 busy。"""
    if not SERIAL_LOCK.acquire(blocking=bool(wait_lock), timeout=120 if wait_lock else None):
        return {"status": "fail", "reason": "已有执行在进行中（串行保护），请稍后重试",
                "steps": [], "tasks": [], "summary": {}, "profile": {}}
    try:
        cred, err = core.load_cred(account)
        if err:
            return {"status": "fail", "reason": err, "steps": [], "tasks": [], "summary": {}, "profile": {}}
        return run_tasks(cred, account, cfg)
    finally:
        SERIAL_LOCK.release()
