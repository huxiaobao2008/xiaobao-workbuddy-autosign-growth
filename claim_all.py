#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键领取所有账号的**可领积分**（纯 API，不需要切换客户端登录账号）。

背景：UI 驱动把任务"做完"之后，积分是**待领取**状态，必须再调领取接口才算到账。
以前这一步只挂在 batch_runner 里，单跑 UI 任务时容易漏 → 用户会发现
"任务做完了但积分没领"。这个脚本就是那个缺的收尾动作。

行为：对每个账号依次
  1) 拉任务列表（服务端最新状态）
  2) 跳过 已领取 / 需付费 / 已锁定 / 已过期
  3) 未接取的先接取；已完成未领取的领取
  4) 打印本次到账积分与余额变化
**不会**驱动客户端 UI，所以可以随时跑、不会打断正在进行的界面操作。

用法：
    python claim_all.py                    # 配置里的所有账号
    python claim_all.py account_e          # 只领某个账号
    python claim_all.py account_d account_f
    python claim_all.py --json             # 输出 JSON（给脚本/自动化用）
"""
import json
import sys

import auto_buddy as core
import tasks as T


def claim_account(account, cfg, quiet=False):
    r = T.run_account_tasks(account, cfg)
    s = r.get("summary") or {}
    out = {
        "account": account.get("key"),
        "label": account.get("label") or account.get("nickname"),
        "status": r.get("status"),
        "reason": r.get("reason"),
        "claimed": s.get("claimed"),
        "accepted": s.get("accepted"),
        "credit_got": r.get("credit_got"),
        "balance_before": r.get("balance_before"),
        "balance_after": r.get("balance_after"),
        "balance_delta": r.get("balance_delta"),
    }
    if not quiet:
        print("== %s（%s）  %s" % (out["account"], out["label"], out["status"] or "-"), flush=True)
        print("   领取 %s 项 | 本次到账 %s 积分 | 余额 %s -> %s（%s）"
              % (out["claimed"], out["credit_got"],
                 out["balance_before"], out["balance_after"], out["balance_delta"]),
              flush=True)
        if out["reason"]:
            print("   说明：%s" % out["reason"], flush=True)
    return out


def main():
    argv = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    cfg = core.load_config()
    accounts = cfg.get("accounts") or []
    if argv:
        want = set(argv)
        accounts = [a for a in accounts if a.get("key") in want]
        missing = want - {a.get("key") for a in accounts}
        for m in sorted(missing):
            print("!! 配置里没有账号 %s" % m, flush=True)

    results = []
    total = 0
    for a in accounts:
        try:
            r = claim_account(a, cfg, quiet=as_json)
        except Exception as e:                      # 单账号失败不影响其余账号
            r = {"account": a.get("key"), "status": "fail",
                 "reason": "%s: %s" % (type(e).__name__, str(e)[:200])}
            if not as_json:
                print("!! %s 异常：%s" % (a.get("key"), r["reason"]), flush=True)
        results.append(r)
        total += int(r.get("credit_got") or 0)

    if as_json:
        print(json.dumps({"total_credit_got": total, "accounts": results},
                         ensure_ascii=False, indent=2))
    else:
        print()
        print("合计本次到账：%d 积分" % total, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
