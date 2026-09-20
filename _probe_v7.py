# -*- coding: utf-8 -*-
"""探针 v7：验证**生产路径**（do_expert_team_3，不显式传 model）是否会自动选对档。

v6 已经证明：同一个团队，Hy3 → 10 分钟挂死不计数；Deepseek-V4.1-Flash → 130 秒跑完并 +1。
v7 要验证的是「接线」—— do_expert_team_3 不带 model 参数时，
run_expert_once 里的 `if model is None and kind == 'team': model = TEAM_MODEL`
是否真的生效（否则又会退回 Hy3，重演挂死）。

用法: python _probe_v7.py <account_key> [start]
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import auto_buddy as core      # noqa: E402
import account_switch as AS    # noqa: E402
import tasks as T              # noqa: E402
import ui_tasks as UT          # noqa: E402


def progress(key):
    cfg = core.load_config()
    acc = next((a for a in cfg["accounts"] if a["key"] == key), None)
    cred, _ = core.load_cred(acc)
    tl, _ = T.fetch_tasks(cred, cfg)
    for t in (tl or []):
        if t.get("code") == "Expert_team_use_3":
            return t.get("progress_text")
    return None


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "account_g"
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    print("[TEAM_MODEL] %s" % UT.TEAM_MODEL, flush=True)
    print("[before] %s team3=%s" % (key, progress(key)), flush=True)
    sw = AS.switch_to(key, reload=False, verify=True)
    print("[switch] ok=%s" % sw.get("ok"), flush=True)

    t0 = time.time()
    # 生产路径：**不传 model**，看它能不能自己挑到 TEAM_MODEL
    r = UT.do_expert_team_3(need=1, start=start, delete_after=True, budget=600)
    dt = time.time() - t0

    print("[result] secs=%.0f ok=%s n_ok=%s err=%s" % (dt, r.get("ok"), r.get("n_ok"), r.get("err")), flush=True)
    for x in (r.get("runs") or []):
        print("[run] team=%s summoned=%s ok=%s deleted=%s err=%s"
              % (x.get("team"), x.get("summoned"), x.get("ok"), x.get("deleted"), x.get("err")), flush=True)

    time.sleep(3)
    print("[after]  %s team3=%s" % (key, progress(key)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
