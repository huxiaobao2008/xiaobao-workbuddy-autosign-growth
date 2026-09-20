# -*- coding: utf-8 -*-
"""清理：删掉「今天为完成成长任务而产生的」会话。

安全设计：
  - **白名单驱动**：只按下面 TARGETS 里逐条列出的标题片段删，绝不按「第 N 条」或「最新一条」删。
  - 每个账号删前后各列一次清单，删了什么一目了然。
  - 切号带重试（客户端侧边栏是延迟重绘的，一次校验失败很常见，不代表真的切不过去）。
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import account_switch as AS    # noqa: E402
import ui_driver as U          # noqa: E402

# 账号 -> 要删的标题片段（只会删「包含该片段」的会话）
TARGETS = {
    "account_e": [
        "帮我开发一个贪吃蛇游戏",
        "帮我把游戏项目当工作室来推进",
        "我想从零做一个团队协作工具",
    ],
    "account_h": [
        "用一句话回答",
        "用一句话说一个厨房生活小技巧",
        "把这句话整理成一句话",
        "「AI 发展趋势",
        "请求Godot工程师实现游戏功能",
    ],
}


def switch(k, tries=4):
    r = None
    for _ in range(tries):
        r = AS.switch_to(k, reload=False, verify=True)
        if r.get("ok"):
            return r
        time.sleep(3)
    return r or {"ok": False, "err": "unknown"}


def titles():
    return [c.get("title") or "" for c in (U.conversations() or [])]


def stable_titles(tries=10, gap=1.2):
    """等侧边栏重绘完成再取列表。

    坑（真踩过）：刚切完账号立刻读，会拿到**空列表**（侧边栏还没重绘）。
    用它去算「要删哪些」→ victims 为空 → 一条都没删还以为成功了。
    所以必须连续两次读到相同且非空才算稳定。
    """
    prev = None
    for _ in range(tries):
        cur = titles()
        if cur and cur == prev:
            return cur
        prev = cur
        time.sleep(gap)
    return prev or []


def main():
    for key, signs in TARGETS.items():
        sw = switch(key)
        print("==== %s  switch ok=%s menu=%s" % (key, sw.get("ok"), (sw.get("after") or {}).get("menu")), flush=True)
        if not sw.get("ok"):
            print("     跳过（切号失败，未做任何删除）", flush=True)
            continue
        before = stable_titles()
        print("   删除前 %d 条" % len(before), flush=True)
        if not before:
            print("     列表为空且不稳定，跳过（不做任何删除）", flush=True)
            continue
        victims = [t for t in before if any(s in t for s in signs)]
        for t in victims:
            print("   [-] %s" % t[:90], flush=True)
        for t in victims:
            r = U.delete_conversation(t)
            print("       -> %s" % json.dumps(r, ensure_ascii=False)[:120], flush=True)
            time.sleep(1.5)
        after = stable_titles()
        print("   删除后 %d 条：%s" % (len(after), json.dumps(after, ensure_ascii=False)[:400]), flush=True)
        left = [t for t in after if any(s in t for s in signs)]
        print("   仍残留 %d 条：%s" % (len(left), json.dumps(left, ensure_ascii=False)[:300]), flush=True)
    # 回主号
    r = switch("account_a")
    print("==== 切回 account_a ok=%s" % r.get("ok"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
