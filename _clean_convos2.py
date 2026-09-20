# -*- coding: utf-8 -*-
"""清理 v2：反复删到没有为止（侧边栏是滚动加载的，删一批会露出下一批）。

安全设计：
  - **只按标题签名匹配**，签名全部来自「自动化任务提示词」的特征（模板名 + 我们写的短指令）。
  - **排除 account_a / account_b**（用户自己在用的主号/副号），一个都不动。
  - 每个账号删完再列一次，残留数量报出来。
  - 切号带重试 + 列表稳定性等待（否则会读到空列表 → 一条都不删还以为成功）。
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import auto_buddy as core      # noqa: E402
import account_switch as AS    # noqa: E402
import ui_driver as U          # noqa: E402

SKIP_ACCOUNTS = {"account_a", "account_b"}     # 用户自己在用，绝不碰

# 自动化提示词特征（命中即视为「为完成任务而建的会话」）
SIGNS = [
    "用一句话简单介绍你自己",
    "用一句话回答",
    "用一句话说一个厨房生活小技巧",
    "把这句话整理成一句话",
    "用一句话说明 MVP 的核心思想",
    "用两句话说明什么是碳中和",
    "用一句话说一个厨房",
    "「AI 发展趋势",
    "请求Godot工程师实现游戏功能",
    "获取今日可用时间管理建议",
    "帮我开发一个贪吃蛇游戏",
    "帮我把游戏项目当工作室来推进",
    "我想从零做一个团队协作工具",
    "帮我确定新产品的品牌视觉方向",
    "直接给结论，不要展开调研",
    "直接给结果，不要",
    "一句话回答。",
    "每天推荐一句",
    # 第二轮补充（第一轮漏掉的、确认属于自动化/诊断的标题）
    "请使用资料库的能力",
    "一键做同款",
    "查询今天日期",
    "幻灯片 只要一页",
    "确定新产品品牌视觉",
    "我们需要开发微信小程序",
    "开发贪吃蛇与规划杭州旅行",
    "从零开发团队协作工具",
    "<task-notification>",
]


def switch(k, tries=5):
    r = None
    for _ in range(tries):
        r = AS.switch_to(k, reload=False, verify=True)
        if r.get("ok"):
            return r
        time.sleep(2.5)
    return r or {"ok": False, "err": "unknown"}


def titles():
    return [c.get("title") or "" for c in (U.conversations() or [])]


def stable_titles(tries=14, gap=1.5):
    """等到「连续两次读到相同且非空」为止。

    列表为空有两种原因：真的没有会话，或者侧边栏还没重绘。空列表时**继续等**
    （宁可多等几轮，也不要因为读到空列表就跳过、或者把空列表当成"没有残留"）。
    """
    prev = None
    empties = 0
    for i in range(tries):
        cur = titles()
        if cur and cur == prev:
            return cur
        if not cur:
            empties += 1
            if empties >= 4:          # 连续 4 次都是空 → 认定这个号确实没有会话
                return []
        else:
            empties = 0
        prev = cur
        time.sleep(gap)
    return prev or []


def matched(ts):
    return [t for t in ts if any(s in t for s in SIGNS)]


def main():
    cfg = core.load_config()
    keys = [a["key"] for a in cfg["accounts"] if a.get("enabled", True) and a["key"] not in SKIP_ACCOUNTS]
    print("清理范围（跳过 %s）：%s" % (", ".join(sorted(SKIP_ACCOUNTS)), ", ".join(keys)), flush=True)

    grand = 0
    for k in keys:
        sw = switch(k)
        print("== %s switch=%s menu=%s" % (k, sw.get("ok"), (sw.get("after") or {}).get("menu")), flush=True)
        if not sw.get("ok"):
            print("   切号失败，未做删除", flush=True)
            continue
        t0 = stable_titles()
        if not t0:
            print("   列表读不到（不稳定），未做删除", flush=True)
            continue
        print("   初始 %d 条：%s" % (len(t0), json.dumps(t0, ensure_ascii=False)[:300]), flush=True)
        deleted = 0
        for rnd in range(8):
            ts = stable_titles()
            victims = matched(ts)
            if not victims:
                break
            for t in victims:
                r = U.delete_conversation(t)
                ok = isinstance(r, dict) and r.get("ok")
                print("   [-%d] %s -> ok=%s" % (rnd, t[:70], ok), flush=True)
                if ok:
                    deleted += 1
                time.sleep(1.2)
        left = matched(stable_titles())
        print("   删除 %d 条，残留 %d 条 %s" % (deleted, len(left), json.dumps(left, ensure_ascii=False)[:250]), flush=True)
        grand += deleted

    print("合计删除 %d 条" % grand, flush=True)
    print("切回 account_a ok=%s" % switch("account_a").get("ok"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
