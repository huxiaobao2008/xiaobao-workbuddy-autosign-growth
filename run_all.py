#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Buddy 加油站 - 一键全自动（签到 + 成长任务 + 领积分 + 出行奖励），覆盖所有启用账号。

为什么要这个脚本：
  原来「每日全自动」散在 auto_buddy(签到) / tasks(成长引擎) / batch_runner(界面类任务)
  / claim_all(收尾领取) 四个入口，没有一个能把"签到 + 任务 + 领所有积分 + 出行"一次性跑完。
  这个脚本把它们按顺序串起来，给桌面一键启动器和网页界面的「一键全自动」按钮共用。

四阶段：
  1) 确保客户端带 CDP 调试端口（没有就拉起 client_cdp.py --restart）。
  2) API 管线（纯接口，不碰客户端）：core.run_account
       每日签到 / 出行到达奖励 / 成长任务清单 / 成长热度点亮。
  3) UI 类任务（需在客户端界面点）：逐账号切号，batch_runner.run_account
       template_5 / Model_chat_GLM5.2 / 专家 / 灵感 / 画布 / 应用 ... 并当场领取。
  4) 收尾领取：claim_all 扫一遍所有账号，把漏领的积分领到手。

可作为模块被 server.py 的 /api/run-all 在后台线程调用（传入 progress 回调拿实时进度）。
也可命令行直接跑：python run_all.py
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auto_buddy as core          # noqa: E402
import tasks as T                  # noqa: E402
import account_switch as AS        # noqa: E402
import batch_runner as BR          # noqa: E402
import claim_all as CA             # noqa: E402

BASE_DIR = core.BASE_DIR
LOG_DIR = core.LOG_DIR
CDP_PORT = 9222

# 「停止任务」信号文件：server 的停止按钮写它，run_all（独立进程）各步骤前检查它。
# 用文件而不是内存标志，是因为 run_all 是 server 的**子进程**，内存变量不共享。
STOP_FILE = os.path.join(LOG_DIR, "STOP_ALL")


def _stop():
    return os.path.exists(STOP_FILE)

# 单账号 UI 任务的时间预算（秒）。任一账号卡死（如额度耗尽的专家团）都不会
# 拖垮整批，也不会卡住「切回主号」——达到预算就跳过该账号剩余任务。
ACCOUNT_BUDGET = 15 * 60

PY = (core.load_config().get("python_path")
      or os.environ.get("PYTHON", "")
      or sys.executable)


def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _switch_back_main(p, restore_key, accounts):
    """保证把客户端交还给「运行前正在用的那个账号」（无论 UI 任务成功/超时/异常）。

    这是修复「遇到专家团队就卡住、还切不回主号、显示连接不上」的核心：
    原先切回逻辑在 UI 循环**之后**，一旦某个账号卡死就永远跑不到；而且即便跑完，
    若主号本身也在启用列表里，旧逻辑就「跳过切回」，结果客户端停在最后一个被驱动的
    账号上，并不是用户原来的账号。现在放进 run_all 的 finally，并且**无条件**切回
    restore_key（运行前活跃的那个账号），保证用户回来时客户端还是他原来的样子。
    """
    if not restore_key:
        return
    try:
        back = AS.switch_to(restore_key, reload=False)
        p("ui", "已切回运行前账号 %s（ok=%s）" % (restore_key, back.get("ok")))
    except Exception as e:
        p("ui", "切回原账号失败：%s —— 客户端可能已关闭或 CDP 不可达；"
                 "请双击 restart-cdp.cmd 重启客户端后手动切回 %s" % (e, restore_key))


def ensure_client(timeout=150):
    """确保客户端带 CDP 端口(9222)启动；已开则跳过，未开则拉起。返回 True/False。"""
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/json/version" % CDP_PORT, timeout=2)
        return True
    except Exception:
        pass
    script = os.path.join(BASE_DIR, "client_cdp.py")
    if not os.path.exists(script):
        return False
    print("[%s] 客户端未带调试端口，正在拉起（restart --wait %d）…" % (_ts(), timeout), flush=True)
    try:
        import subprocess
        subprocess.run([PY, script, "--restart", "--wait", str(timeout)],
                       cwd=BASE_DIR, timeout=timeout + 30)
    except Exception as e:
        print("[%s] 拉起客户端失败：%s" % (_ts(), e), flush=True)
        return False
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/json/version" % CDP_PORT, timeout=2)
        return True
    except Exception:
        return False


def order_accounts_by_need(accounts, cfg, p=None):
    """按「成长任务完成数最少 → 最多」排序，落后号优先跑。

    为什么必须这样（用户 2026-09-21 指出）：按配置顺序跑时，每次都先跑已完成
    16/19 的"尖子号"，等时间/额度耗尽，只剩 6/19 的落后号从来轮不到执行。
    读取失败的账号排最后（无法判断需求，不抢占前面的名额）。
    """
    say = p or (lambda *a, **k: None)
    scored = []
    for a in accounts:
        try:
            cred, _ = core.load_cred(a)
            if not cred:
                scored.append((10 ** 6, 0, 0, a))
                continue
            tl, err = T.fetch_tasks(cred, cfg)
            if err:
                scored.append((10 ** 6 - 1, 0, 0, a))
                continue
            s = T.summarize(tl)
            done = int(s.get("done") or 0)
            total = int(s.get("total") or 0)
            # 剩余越多越靠前：用「已完成的负数」做升序键
            scored.append((-total + done, done, total, a))
        except Exception:
            scored.append((10 ** 6 - 2, 0, 0, a))
    scored.sort(key=lambda x: (x[0], x[1]))
    ordered = [x[3] for x in scored]
    brief = []
    for _k, done, total, a in scored:
        if total:
            brief.append("%s %d/%d" % (a["key"], done, total))
        else:
            brief.append("%s 未知" % a["key"])
    say("order", "执行顺序（完成最少→最多）：%s" % " → ".join(brief))
    return ordered


def run_all(progress=None):
    """跑完整流程。progress(stage, msg) 可选回调。返回汇总 dict。"""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    logpath = os.path.join(LOG_DIR, "run_all_%s.log" % ts)
    os.makedirs(LOG_DIR, exist_ok=True)
    f = open(logpath, "a", encoding="utf-8")

    # 清掉上一轮可能残留的「停止」标记，保证本轮能正常跑
    try:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
    except Exception:
        pass

    summary = {"ts": ts, "log": logpath, "accounts": [], "claim_total": 0,
               "client_ok": False, "ui_results": {}, "claim_results": []}

    def p(stage, msg):
        line = "[%s][%s] %s" % (datetime.now().strftime("%H:%M:%S"), stage, msg)
        print(line, flush=True)
        try:
            f.write(line + "\n")
            f.flush()
        except Exception:
            pass
        if progress:
            try:
                progress(stage, msg)
            except Exception:
                pass

    try:
        cfg = core.load_config()
        accounts = [a for a in cfg["accounts"] if a.get("enabled", True)]
        p("start", "启用账号 %d 个：%s" % (len(accounts), ", ".join(a["key"] for a in accounts)))
        # ★ 执行顺序：完成数**最少**的账号排最前（用户 2026-09-21 要求）。
        #   旧行为固定按配置顺序跑，于是每次都先啃已经 16/19 的号，
        #   时间和额度耗完时，只完成 6/19 的落后号永远轮不到。
        accounts = order_accounts_by_need(accounts, cfg, p)

        # 1) 客户端
        summary["client_ok"] = ensure_client()
        if summary["client_ok"]:
            p("client", "客户端已就绪（CDP 端口 %d）" % CDP_PORT)
        else:
            p("client", "客户端未就绪（CDP %d 不可达）：UI 类任务将跳过，仅跑 API 管线" % CDP_PORT)

        # 记录切号前的当前账号，跑完 UI 任务后切回去
        restore_key = None
        if summary["client_ok"]:
            try:
                restore_key = AS.current_key()[0]
            except Exception:
                restore_key = None

        # 2) API 管线（签到 / 出行 / 成长任务 / 热度）
        p("api", "===== 阶段一：API 管线（签到 / 出行奖励 / 成长任务 / 热度）=====")
        for a in accounts:
            try:
                r = core.run_account(a, cfg)
                st = r.get("status")
                p("api:%s" % a["key"], "%s | %s" % (st, r.get("reason")))
                summary["accounts"].append({"key": a["key"], "api": st,
                                            "reason": r.get("reason")})
            except Exception as e:
                p("api:%s" % a["key"], "异常：%s: %s" % (type(e).__name__, e))
                summary["accounts"].append({"key": a["key"], "api": "fail",
                                            "reason": "%s: %s" % (type(e).__name__, e)})

        # 3) UI 类任务（逐账号切号驱动）——**循环直到所有账号成长任务完成**才收工
        #    （用户 2026-09-21 要求：没手动停止就应该自动循环所有账号直到全部完成，
        #     而不是一轮没做完就收摊。轮数上限 RUN_ALL_UI_ROUNDS，默认 3。）
        ui_claim_total = 0
        if summary["client_ok"]:
            max_rounds = int(os.environ.get("RUN_ALL_UI_ROUNDS", "3"))
            for round_no in range(1, max_rounds + 1):
                if _stop():
                    p("ui", "[停止] 收到停止指令，中止 UI 轮次")
                    break
                if round_no > 1:
                    p("ui", "===== 阶段二·第 %d 轮（复核全部账号，未完成的重跑）=====" % round_no)
                codes = ["template_5", "Model_chat_GLM5.2"] + list(BR.UI_CODES)
                all_done = True
                try:
                    for a in accounts:
                        # 智能跳过：已完成且无待领积分的账号，不再驱动 UI 任务
                        # （省时间/省额度），但签到已在阶段一跑过、照常保留。
                        try:
                            cred, _ = core.load_cred(a)
                            if cred:
                                tl, _ = T.fetch_tasks(cred, cfg)
                                ts = T.summarize(tl)
                                if ts.get("total") and ts.get("done") == ts.get("total") \
                                        and not ts.get("pending_credit"):
                                    p("ui:%s" % a["key"],
                                      "成长任务已全部完成（%d/%d），跳过 UI 任务驱动（仅保留签到）"
                                      % (ts["done"], ts["total"]))
                                    continue
                        except Exception as e:
                            p("ui:%s" % a["key"], "任务状态读取失败，仍尝试驱动：%s" % e)
                        # 本账号还要跑 → 本轮不算"全部完成"
                        all_done = False
                        # 每账号单设时间预算：任一账号卡死都不会拖垮整批，
                        # 也不会卡住后面的「切回主号」（切回在 finally 里做）。
                        deadline = time.time() + ACCOUNT_BUDGET
                        try:
                            out = BR.run_account(a["key"], codes, BR.TEMPLATE_POOL,
                                                  do_claim=True, do_delete=True, dry=False,
                                                  deadline=deadline,
                                                  log=lambda m: p("ui:%s" % a["key"], m))
                            err = out.get("err")
                            sw = (out.get("switch") or {}).get("ok")
                            # 阶段二当场领取的积分也要计入本次总账
                            ui_got = int((out.get("claim") or {}).get("credit_got") or 0)
                            ui_claim_total += ui_got
                            p("ui:%s" % a["key"], "切号 ok=%s | %s" % (sw, err or "完成"))
                            summary["ui_results"]["%s@r%d" % (a["key"], round_no)] = err or "ok"
                        except Exception as e:
                            p("ui:%s" % a["key"], "异常：%s: %s" % (type(e).__name__, e))
                            summary["ui_results"][a["key"]] = "异常：%s" % e
                        # ★ 收尾清理（用户 2026-09-21 规则）：只有**任务全部完成、
                        #   积分全部到手**之后才删该账号的自动化遗留会话；
                        #   没完成就留着，等下一轮再跑。
                        try:
                            ready, why = BR.account_ready_for_cleanup(a, cfg)
                            if ready:
                                n = BR._cleanup_team_convs(
                                    log=lambda m: p("ui:%s" % a["key"], m))
                                p("ui:%s" % a["key"], "%s → 清理遗留会话 %d 条" % (why, len(n)))
                                summary.setdefault("cleanup", {})[a["key"]] = len(n)
                            else:
                                p("ui:%s" % a["key"], "不清理：%s" % why)
                        except Exception as e:
                            p("ui:%s" % a["key"], "清理检查异常：%s" % str(e)[:80])
                finally:
                    # 核心修复：无论 UI 阶段是否超时/异常，都把客户端交还主号，
                    # 否则会卡在最后一个被驱动的账号、UI 显示「连接不上」。
                    _switch_back_main(p, restore_key, accounts)
                if all_done:
                    p("ui", "第 %d 轮结束：所有账号成长任务均已完成，UI 阶段收工" % round_no)
                    break
                if round_no == max_rounds:
                    p("ui", "已达最大轮数 %d（RUN_ALL_UI_ROUNDS），仍有未完成账号——下轮定时任务会继续" % max_rounds)
        else:
            p("ui", "跳过 UI 类任务（客户端未就绪）")

        # 4) 收尾领取
        p("claim", "===== 阶段三：收尾领取（claim_all，领所有可领积分）=====")
        claim_all_total = 0
        for a in accounts:
            if _stop():
                p("claim", "[停止] 收到停止指令，中止收尾领取")
                break
            try:
                r = CA.claim_account(a, cfg, quiet=True)
                got = int(r.get("credit_got") or 0)
                claim_all_total += got
                summary["claim_results"].append({"key": a["key"],
                                                 "claimed": r.get("claimed"),
                                                 "credit_got": got,
                                                 "status": r.get("status")})
                p("claim:%s" % a["key"], "领取 %s 项 | 本次到账 %s 积分" % (r.get("claimed"), got))
            except Exception as e:
                p("claim:%s" % a["key"], "异常：%s: %s" % (type(e).__name__, e))
                summary["claim_results"].append({"key": a["key"], "credit_got": 0,
                                                 "status": "fail", "reason": str(e)[:200]})
        summary["claim_total"] = ui_claim_total + claim_all_total
        summary["ui_claim_total"] = ui_claim_total
        summary["claim_all_total"] = claim_all_total
        p("done", "全部完成。阶段二领取 %d 积分，阶段三领取 %d 积分，本次共领取 %d 积分。日志：%s"
          % (ui_claim_total, claim_all_total, summary["claim_total"], logpath))
        return summary
    finally:
        try:
            f.close()
        except Exception:
            pass


def main():
    run_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
