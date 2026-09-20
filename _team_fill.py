# -*- coding: utf-8 -*-
"""专家团填充器：边测边跑，逐个候选团队试，直到该账号 Expert_team_use_3 达标。

背景（2026-09-19 真机实验结论）：
  专家团计分的**唯一条件 = 团队真的把这一轮说完（客户端标记「已完成」）**。
  两类团队表现完全不同：
    A. 「菜单/起手卡」型（如 独董会 idx6）：给一张卡片就收尾 → 130s 完成 → **计分**。
    B. 「多阶段长流程」型（MVP开发专家团 idx0 等）：一直 processing，
       实测 Deepseek-V4.1-Flash 跑 484s 仍未结束 → **不计分**。
  另外模型也是硬条件：免费 Hy3 即使 A 类团队也会挂死 10 分钟不结束。
  → 所以本脚本默认用 TEAM_MODEL（Deepseek-V4.1-Flash），并按候选顺序试。

用法:
  python _team_fill.py <account_key> [target] [idx,idx,...]
  python _team_fill.py account_g 3
  python _team_fill.py account_g 1 6,9,10
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import auto_buddy as core      # noqa: E402
import account_switch as AS    # noqa: E402
import tasks as T              # noqa: E402
import ui_tasks as UT          # noqa: E402

# 候选团队（按「是否会自己收尾」的经验排序，先试最可能成功的）
#   6 独董会            —— 已实测成功（130s 完成 +1）
#   9 智数分析专家团     —— 6 人、自然语言转SQL/建模，偏「给方案」型
#   10 工程保障团队      —— 5 人、以「评估/审查」为主
#   5 腾讯云技术支持     —— 问答型，预期短
#   7 软件工坊           —— 审查型
#   1 软件开发团队       —— 偏实施（风险）
#   11 科研专家团 / 8 深度研究 / 4 内容创作 / 3 交易分析 / 2 游戏工作室 / 0 MVP
DEFAULT_CANDIDATES = [6, 9, 10, 5, 7, 1, 11, 8, 4, 3, 2, 0]

TEAM_NAMES = {
    0: "MVP开发专家团", 1: "软件开发团队", 2: "游戏开发工作室", 3: "交易分析团队",
    4: "内容创作专家团", 5: "腾讯云技术支持", 6: "独董会", 7: "软件工坊",
    8: "深度研究团队", 9: "智数分析专家团", 10: "工程保障团队", 11: "科研专家团",
}


def progress(key):
    cfg = core.load_config()
    acc = next((a for a in cfg["accounts"] if a["key"] == key), None)
    cred, _ = core.load_cred(acc)
    tl, _ = T.fetch_tasks(cred, cfg)
    for t in (tl or []):
        if t.get("code") == "Expert_team_use_3":
            p = t.get("progress") or {}
            return p.get("current"), t.get("progress_text")
    return None, None


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "account_g"
    target = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    if len(sys.argv) > 3 and sys.argv[3].strip():
        cands = [int(x) for x in sys.argv[3].split(",") if x.strip()]
    else:
        cands = list(DEFAULT_CANDIDATES)

    cur, txt = progress(key)
    print("[before] %s team3=%s" % (key, txt), flush=True)
    if (cur or 0) >= target:
        print("[skip] 已达标", flush=True)
        return 0

    sw = AS.switch_to(key, reload=False, verify=True)
    print("[switch] ok=%s" % sw.get("ok"), flush=True)
    if not sw.get("ok"):
        print("[abort] 切号失败", flush=True)
        return 1

    tried, good, bad = [], [], []
    for idx in cands:
        cur, txt = progress(key)
        if (cur or 0) >= target:
            break
        name = TEAM_NAMES.get(idx, "?%d" % idx)
        t0 = time.time()
        r = UT.run_expert_once(kind="team", idx=idx, prompt="",
                               max_wait=300, delete_after=True)
        run = r.get("run") or {}
        dt = time.time() - t0
        cur2, txt2 = progress(key)
        gained = (cur2 or 0) - (cur or 0)
        tried.append(idx)
        print("[try] idx=%d %s secs=%.0f sent=%s done=%s reason=%s -> %s (delta=%+d)"
              % (idx, name, dt, r.get("sent"), run.get("done"), run.get("reason"),
                 txt2, gained), flush=True)
        if gained > 0:
            good.append(idx)
        else:
            bad.append(idx)
        time.sleep(1.5)

    cur, txt = progress(key)
    print("[after] %s team3=%s" % (key, txt), flush=True)
    print("[good] %s" % good, flush=True)
    print("[bad]  %s" % bad, flush=True)
    print("[tried] %s" % tried, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
