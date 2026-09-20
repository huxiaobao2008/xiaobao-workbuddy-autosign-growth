# -*- coding: utf-8 -*-
"""只读：逐个切换账号，列出客户端侧边栏里的全部会话（标题 + 时间 + 是否可删）。

不删除任何东西。用于「清理前给用户过目」。
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import auto_buddy as core      # noqa: E402
import account_switch as AS    # noqa: E402
import ui_driver as U          # noqa: E402

# 明确属于「自动化/诊断」产生的会话特征（用于后面的清理判定，这里只做标记）
TEST_SIGNS = [
    "用一句话简单介绍你自己",
    "从零做一个团队协作工具",
    "从零开发团队协作工具",
    "开发贪吃蛇",
    "帮我把游戏项目当工作室来推进",
    "帮我开发一个贪吃蛇游戏",
    "杭州旅行",
    "帮我确定新产品的品牌视觉方向",
    "做同款",
    "全球人口",
    "运行 team 专家任务",
]


def main():
    cfg = core.load_config()
    keys = [a["key"] for a in cfg["accounts"] if a.get("enabled", True)]
    print("待扫描账号 %d 个：%s" % (len(keys), ", ".join(keys)), flush=True)
    total = 0
    for k in keys:
        try:
            sw = AS.switch_to(k, reload=False, verify=True)
            if not sw.get("ok"):
                print("== %s  切换失败：%s" % (k, sw.get("err")), flush=True)
                continue
            time.sleep(1.0)
            cl = U.conversations() or []
            print("== %s  (%s)  会话 %d 条" % (k, (sw.get("after") or {}).get("menu"), len(cl)), flush=True)
            for c in cl:
                t = c.get("title") or ""
                mark = "TEST?" if any(s in t for s in TEST_SIGNS) else "     "
                print("   [%s] %s" % (mark, t), flush=True)
                total += 1
        except Exception as e:
            print("== %s  异常：%s: %s" % (k, type(e).__name__, str(e)[:90]), flush=True)
    print("合计 %d 条会话" % total, flush=True)
    AS.switch_to(keys[0], reload=False, verify=True)
    print("已切回 %s" % keys[0], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
