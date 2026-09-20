# -*- coding: utf-8 -*-
"""删除当前账号里经判定确认的自动化遗留会话（6 条），删完核验。"""
import time

import ui_driver as U

# 已逐条打开核对：首条均含自动化专属指令「执行规则：如果上面的任务需要我提供材料…」
TARGETS = [
    "开发贪吃蛇游戏执行规则",
    "生成建筑施工图设计说明执行规则",
    "设计内容变现方案执行规则",
    "执行本月企业财税合规检查演示",
    "设计账号内容变现执行规则",
    "编写功能规格书竞品与路线图",
]

done, failed = [], []
for t in TARGETS:
    try:
        U.delete_conversation(t, force=False)
        done.append(t)
    except Exception as e:
        failed.append((t, str(e)[:80]))
    time.sleep(1.2)

print("已删除 %d 条：" % len(done))
for t in done:
    print("   -", t)
if failed:
    print("删除失败 %d 条（受保护/当前使用中）：" % len(failed))
    for t, why in failed:
        print("   -", t, "|", why)

time.sleep(2)
left = [x for x in (U.task_titles() or []) if "执行规则" in x]
print("\n剩余含「执行规则」的会话: %d" % len(left))
for t in left:
    print("   *", t[:60])
print("会话总数: %d" % len(U.task_titles() or []))
