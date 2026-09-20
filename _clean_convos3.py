# -*- coding: utf-8 -*-
"""清理 v3：先列清单（默认只读），确认后再删。

v2 的教训：直接删容易误伤（签名漏了就会漏删，签名宽了就会误删）。
v3 改成两段式：
  1) 默认**只列不删**，把每个账号的全部会话标题打出来（含是否命中签名）。
  2) 加 `del` 参数才真删，且**只删命中签名的**，并在最后复核残留。

安全设计（继承 v2，不能删）：
  - **排除 account_a / account_b**（用户在用），一个都不动。
  - 切号带重试 + 列表稳定性等待（否则读到空列表 → 以为没残留）。
  - 删除只按标题签名匹配；不认识的标题一律保留并打印出来给人看。

用法:
  python _clean_convos3.py            # 只列
  python _clean_convos3.py del        # 命中签名的才删
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import auto_buddy as core      # noqa: E402
import account_switch as AS    # noqa: E402
import ui_driver as U          # noqa: E402

SKIP_ACCOUNTS = {"account_a", "account_b"}     # 用户自己在用，绝不碰

SIGNS = [
    # --- 模板/单句类（批量刷任务留下的） ---
    "用一句话简单介绍你自己",
    "用一句话回答",
    "用一句话说一个厨房",
    "把这句话整理成一句话",
    "用一句话说明 MVP 的核心思想",
    "用两句话说明什么是碳中和",
    "「AI 发展趋势",
    "一句话回答。",
    "每天推荐一句",
    "查询今天日期",
    # --- 具体任务提示词 ---
    "请求Godot工程师实现游戏功能",
    "获取今日可用时间管理建议",
    "帮我开发一个贪吃蛇游戏",
    "帮我把游戏项目当工作室来推进",
    "帮我确定新产品的品牌视觉方向",
    "直接给结论，不要展开调研",
    "直接给结果，不要",
    "请使用资料库的能力",
    "一键做同款",
    "幻灯片 只要一页",
    "确定新产品品牌视觉",
    "我们需要开发微信小程序",
    "开发贪吃蛇与规划杭州旅行",
    "<task-notification>",
    # --- 专家团自带推荐提示词（2026-09-19 探测留下的） ---
    "我正在做一项关键决策",        # 独董会 idx6
    "独立审议",                    # 独董会 回复关键词
    "我想从零做一个团队协作工具",  # MVP开发专家团 idx0
    "说出你的想法",                # 多个团队的引导语开头
    # --- 第三轮补充：客户端的会话标题会被**改写/截断**，所以上面那些"整句"签名
    #     经常匹配不上（实测漏了 account_g 的 5 条）。这里改用**短关键词**兜住。 ---
    "核心思想",                    # 「说明 MVP 的核心思想」
    "复利",                        # 「用一句话说明什么是复利。只给答案。」
    "平均值",                      # 「计算数字1至5的平均值」
    "今天日期",                    # 「询问今天日期」
    "时间管理建议",                # 「个人工作台 用一句话给我一个今天立刻能用的时间管理建议。」
    "团队协作工具",                # 「制作团队协作工具的自我介绍」
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
    prev = None
    empties = 0
    for _ in range(tries):
        cur = titles()
        if cur and cur == prev:
            return cur
        if not cur:
            empties += 1
            if empties >= 4:
                return []
        else:
            empties = 0
        prev = cur
        time.sleep(gap)
    return prev or []


def matched(ts):
    return [t for t in ts if any(s in t for s in SIGNS)]


def main():
    do_del = len(sys.argv) > 1 and sys.argv[1] == "del"
    cfg = core.load_config()
    keys = [a["key"] for a in cfg["accounts"]
            if a.get("enabled", True) and a["key"] not in SKIP_ACCOUNTS]
    print("模式=%s；范围（跳过 %s）：%s"
          % ("删除" if do_del else "只列", ", ".join(sorted(SKIP_ACCOUNTS)), ", ".join(keys)), flush=True)

    grand = 0
    report = {}
    for k in keys:
        sw = switch(k)
        if not sw.get("ok"):
            print("== %s 切号失败，跳过" % k, flush=True)
            continue
        ts = stable_titles()
        hit = matched(ts)
        report[k] = {"total": len(ts), "hit": hit, "keep": [t for t in ts if t not in hit]}
        print("== %s 共 %d 条，命中签名 %d 条" % (k, len(ts), len(hit)), flush=True)
        for t in ts:
            print("   %s %s" % ("[删]" if t in hit else "[留]", t[:78]), flush=True)

        if do_del and hit:
            deleted = 0
            for t in hit:
                r = U.delete_conversation(t)
                ok = isinstance(r, dict) and r.get("ok")
                if ok:
                    deleted += 1
                print("   -> 删除 %s ok=%s" % (t[:60], ok), flush=True)
                time.sleep(1.2)
            left = matched(stable_titles())
            print("   本次删除 %d，残留命中 %d %s"
                  % (deleted, len(left), json.dumps(left, ensure_ascii=False)[:200]), flush=True)
            grand += deleted

    print("---- 汇总 ----", flush=True)
    for k, v in report.items():
        print("%s: 总 %d / 命中 %d / 保留 %d" % (k, v["total"], len(v["hit"]), len(v["keep"])), flush=True)
    if do_del:
        print("合计删除 %d 条" % grand, flush=True)
        print("切回 account_a ok=%s" % switch("account_a").get("ok"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
