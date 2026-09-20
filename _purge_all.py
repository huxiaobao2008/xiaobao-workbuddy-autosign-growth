# -*- coding: utf-8 -*-
"""全账号会话清理：**除了本项目相关会话与「包公偏见」，其它全删**。

安全设计：
  - 默认**只列不删**（跑 `python _purge_all.py` 即可），加 `del` 才真删。
  - 保护名单 `PROTECT` 里的关键词命中的标题**一律不删**（用户点名：包公偏见不动）。
  - 只删「已列出来的标题」，逐条精确删；不认识的标题也会打印出来给人看。
  - 切号带重试 + 列表稳定性等待（侧边栏是懒加载的，读空会误判）。

用法:
  python _purge_all.py            # 只列（含每个账号的全部会话）
  python _purge_all.py del        # 真删（保留 PROTECT）
  python _purge_all.py del keep1,keep2   # 额外保护这些关键词
  python _purge_all.py del --only account_a,account_b  # 只处理指定账号
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import auto_buddy as core      # noqa: E402
import account_switch as AS    # noqa: E402
import ui_driver as U          # noqa: E402

# 用户点名「不动」的东西：本项目相关会话 + 包公偏见
PROTECT = [
    "包公偏见",
    # 下面几个是「咱们今天这个项目」自己的会话（account_a），一律留
    "Buddy加油站双账号每日自动签到与成长任务",
    "实现一键执行签到任务逻辑",
    "补刷 Model_chat_GLM5.2",
    "第一个 全平台 发布任务",
    # 标题太泛、无法判断归属的项目：宁留不删（想删告诉一声即可）
    "继续执行任务",
]

# 这些标题在 ui_driver.PROTECT_TITLES 里（当初被我当成"用户自己的会话"保护起来），
# 但用户已明确点名要删 → 走 force 通道。只列在这里的才 force，绝不全量放开。
FORCE_OK = [
    "短剧转场生硬待优化",
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


def stable_titles(tries=16, gap=1.5):
    prev, empties = None, 0
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


def protected(t, extra):
    return any(k in t for k in (PROTECT + list(extra)))


def main():
    do_del = len(sys.argv) > 1 and sys.argv[1] == "del"
    extra = []
    if len(sys.argv) > 2 and not sys.argv[2].startswith("--"):
        extra = [x.strip() for x in sys.argv[2].split(",") if x.strip()]

    cfg = core.load_config()
    keys = [a["key"] for a in cfg["accounts"]]
    only = ""
    if "--only" in sys.argv:
        i = sys.argv.index("--only")
        if i + 1 < len(sys.argv):
            only = sys.argv[i + 1]
    if only:
        keys = [k for k in keys if k in {x.strip() for x in only.split(",") if x.strip()}]
    print("模式=%s  账号数=%d  保护=%s  额外保护=%s"
          % ("删除" if do_del else "只列", len(keys), PROTECT, extra), flush=True)

    grand, report = 0, {}
    for k in keys:
        sw = switch(k)
        if not sw.get("ok"):
            print("== %s 切号失败，跳过（%s）" % (k, sw.get("err")), flush=True)
            continue
        ts = stable_titles()
        keep = [t for t in ts if protected(t, extra)]
        victims = [t for t in ts if not protected(t, extra)]
        print("== %s 共 %d 条：删 %d / 留 %d" % (k, len(ts), len(victims), len(keep)), flush=True)
        for t in ts:
            print("   %s %s" % ("[留]" if protected(t, extra) else "[删]", t[:76]), flush=True)

        if do_del and victims:
            deleted = 0
            for t in victims:
                force = any(k in t for k in FORCE_OK)
                r = U.delete_conversation(t, force=force)
                ok = isinstance(r, dict) and r.get("ok")
                if ok:
                    deleted += 1
                else:
                    print("   !! 删除失败 %s -> %s" % (t[:50], json.dumps(r, ensure_ascii=False)[:120]),
                          flush=True)
                time.sleep(1.2)
            left = stable_titles()
            print("   本次删除 %d，剩 %d 条：%s" % (deleted, len(left),
                  json.dumps(left, ensure_ascii=False)[:240]), flush=True)
            grand += deleted
            report[k] = {"before": len(ts), "deleted": deleted, "left": left}
        else:
            report[k] = {"before": len(ts), "deleted": 0, "left": ts}

    print("---- 汇总 ----", flush=True)
    for k, v in report.items():
        print("%-10s 原 %d → 删 %d → 剩 %d" % (k, v["before"], v["deleted"], len(v["left"])), flush=True)
    if do_del:
        print("合计删除 %d 条" % grand, flush=True)
        print("切回 account_a ok=%s" % switch("account_a").get("ok"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
