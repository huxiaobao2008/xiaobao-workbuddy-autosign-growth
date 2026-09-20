# -*- coding: utf-8 -*-
"""临时守护：轮询 account_e 的 Expert_team_use_3 进度，到 3/3 自动接取+领取。

背景：2026-09-20 软件工坊团队轮次超出 batch_runner 的 360s 预算后仍在客户端里
继续执行 —— 轮次没失败，只是慢。本脚本只读 API 进度，等服务端计分后自动领奖。
"""
import json
import time

import auto_buddy as core
import tasks as T
import ui_runner as UR

KEY, CODE = "account_e", "Expert_team_use_3"
LOG_PATH = "logs/_poll_claim_1.log"
_logf = open(LOG_PATH, "w", encoding="utf-8")


def log(msg):
    print(msg, flush=True)
    _logf.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
    _logf.flush()


for i in range(45):
    cur, tgt, st = UR.progress_of(KEY, CODE)
    log("poll%d progress=%s/%s (%s)" % (i, cur, tgt, st))
    if cur is not None and tgt is not None and cur >= tgt:
        time.sleep(10)  # 给服务端几秒把状态落稳
        cfg = core.load_config()
        acct = next((a for a in cfg.get("accounts") or [] if a.get("key") == KEY), None)
        res = T.run_account_tasks(acct, cfg)
        log("CLAIM: " + json.dumps(res, ensure_ascii=False)[:800])
        cur2, tgt2, st2 = UR.progress_of(KEY, CODE)
        log("AFTER_CLAIM progress=%s/%s (%s)" % (cur2, tgt2, st2))
        break
    time.sleep(60)
else:
    log("TIMEOUT: 45 分钟内未到 3/3，需人工检查团队会话")
