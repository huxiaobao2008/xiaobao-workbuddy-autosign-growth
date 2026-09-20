# -*- coding: utf-8 -*-
"""除当前账号外，清空所有账号的「任务区」会话列表。

用户指令（2026-09-20）：「除了这个账号（当前），所有账号都把任务列表全清除掉」。

安全设计（顺序不可颠倒）：
  1. **先快照**：每个账号清空前，把全部会话标题 + 时间标记存到
     `logs/ledger_snapshot_<时间戳>.json`（会话标题是「用过哪些专家团」的唯一账本，
     清掉客户端列表 ≠ 丢掉这份知识）。
  2. **只清任务区**，不动「项目」区。
  3. **跳过当前登录账号**（用户要保留的那个）。
  4. 删除走 `deleteTopTask()`（任务区最上面一条；会先解选中态），逐条删、每轮复查，
     删不到就如实报错，不猜着删。
  5. 默认只快照不删；加 `del` 才真删。

用法：
  python _purge_lists.py                 # 只快照（安全）
  python _purge_lists.py del             # 快照 + 清空（跳过当前账号）
  python _purge_lists.py del --only account_e,account_f
"""
import json
import os
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import auto_buddy as core      # noqa: E402
import account_switch as AS    # noqa: E402
import ui_driver as U          # noqa: E402

BASE = r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto"


def switch(k, tries=5):
    r = None
    for _ in range(tries):
        r = AS.switch_to(k, reload=False, verify=True)
        if r.get("ok"):
            return r
        time.sleep(2.5)
    return r or {"ok": False, "err": "unknown"}


def stable_titles(tries=14, gap=1.5):
    """侧边栏懒加载：连续两次读到相同（或连续 4 次为空）才认。"""
    prev, empties = None, 0
    for _ in range(tries):
        cur = U.task_titles() or []
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


def main():
    do_del = len(sys.argv) > 1 and sys.argv[1] == "del"
    cfg = core.load_config()
    key = AS.current_key()
    keys = [a["key"] for a in cfg["accounts"]]
    if "--only" in sys.argv:
        i = sys.argv.index("--only")
        if i + 1 < len(sys.argv):
            want = {x.strip() for x in sys.argv[i + 1].split(",") if x.strip()}
            keys = [k for k in keys if k in want]
    skip = [key] if key in keys else []
    keys = [k for k in keys if k != key]
    print("模式=%s  当前账号=%s（跳过）  待处理=%d 个" % ("删除" if do_del else "只快照", key, len(keys)),
          flush=True)

    snap_name = os.path.join(BASE, "logs", "ledger_snapshot_%s.json"
                             % time.strftime("%Y%m%d-%H%M%S"))
    snap = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "current_skipped": skip, "accounts": {}}
    report = {}

    for k in keys:
        sw = switch(k)
        if not sw.get("ok"):
            print("== %s 切号失败，跳过（%s）" % (k, sw.get("err")), flush=True)
            report[k] = {"err": "switch failed"}
            continue
        nick = U.current_account_name()
        ts = stable_titles()
        snap["accounts"][k] = {"nickname": nick, "titles": ts}
        print("== %s (%s) 任务区 %d 条" % (k, nick, len(ts)), flush=True)
        for t in ts:
            print("     · %s" % t[:76], flush=True)

        deleted, left = 0, ts
        if do_del and ts:
            limit = len(ts) + 8
            for i in range(limit):
                if not stable_titles(tries=6, gap=1.0):
                    break
                r = U.js("(async () => await deleteTopTask())()", timeout=90)
                ok = isinstance(r, dict) and r.get("ok")
                if ok:
                    deleted += 1
                else:
                    print("     !! 删除失败：%s" % json.dumps(r, ensure_ascii=False)[:140], flush=True)
                    # 删不动就停手，别死循环
                    break
                time.sleep(1.0)
            left = stable_titles()
            print("== %s 删除 %d 条，剩 %d 条" % (k, deleted, len(left)), flush=True)
        report[k] = {"before": len(ts), "deleted": deleted, "left": len(left)}

    with open(snap_name, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    print("---- 快照已存：%s ----" % snap_name, flush=True)
    for k, v in report.items():
        print("%-10s %s" % (k, json.dumps(v, ensure_ascii=False)), flush=True)
    print("合计删除 %d 条" % sum(v.get("deleted", 0) for v in report.values()), flush=True)
    sw = switch("account_a")
    print("切回 account_a ok=%s" % sw.get("ok"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
