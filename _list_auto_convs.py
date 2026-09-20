# -*- coding: utf-8 -*-
"""按「自动化指纹」判定当前账号的会话哪些是自动化遗留（可安全清理）。

判定依据：自动化跑任务时用的提示词/模板文案是固定的，用户自己的会话不会包含它们。
只列出命中指纹的会话；未命中的一律不动。
"""
import json

import ui_driver as U
import ui_tasks as UT
import batch_runner as BR

# 自动化专属提示词指纹（取前 16 字做匹配，避免整句标点差异）
FINGERPRINTS = []

# 1) 专家团：召唤团队时追加的自包含执行指令
FINGERPRINTS.append(UT.TEAM_SELF_CONTAINED_PROMPT[:16])
# 2) template_5 的 14 个模板提示词
for _p in U.TEMPLATE_PROMPTS.values():
    FINGERPRINTS.append(str(_p)[:16])
# 3) Model_chat_GLM5.2 的固定提问
FINGERPRINTS.append(BR.CHAT_PROMPT[:16])
# 4) expert_5 的固定提问
FINGERPRINTS.append("用一句话简单介绍你自己")

titles = U.task_titles() or []
hit, miss = [], []
for t in titles:
    t = t or ""
    matched = next((f for f in FINGERPRINTS if f and f in t), None)
    (hit if matched else miss).append((t, matched or ""))

print("会话总数: %d" % len(titles))
print("\n=== 命中自动化指纹（可清理）: %d 条 ===" % len(hit))
for i, (t, f) in enumerate(hit, 1):
    print("  %2d. %-56s  [指纹: %s]" % (i, t[:56], f[:22]))
print("\n=== 未命中（不动，疑为用户会话）: %d 条 ===" % len(miss))
for i, (t, _f) in enumerate(miss, 1):
    print("  %2d. %s" % (i, t[:70]))

with open("logs/_clean_candidates.json", "w", encoding="utf-8") as fh:
    json.dump({"hit": [h[0] for h in hit], "miss": [m[0] for m in miss]}, fh, ensure_ascii=False, indent=1)
print("\n清单已存 logs/_clean_candidates.json")
