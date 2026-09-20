# -*- coding: utf-8 -*-
"""一次性诊断：在指定账号上真实召唤 1 个专家团，发指定指令，看进度是否 +1。

用法:
  python _probe_team.py <account_key> [idx] [prompt] [max_wait]
不传 prompt 时用默认那句「用一句话简单介绍你自己」。
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import auto_buddy as core      # noqa: E402
import account_switch as AS    # noqa: E402
import tasks as T              # noqa: E402
import ui_driver as U          # noqa: E402
import ui_tasks as UT          # noqa: E402


def progress(key):
    cfg = core.load_config()
    acc = next((a for a in cfg["accounts"] if a["key"] == key), None)
    cred, _ = core.load_cred(acc)
    tl, _ = T.fetch_tasks(cred, cfg)
    for t in (tl or []):
        if t.get("code") == "Expert_team_use_3":
            return t.get("progress_text"), t.get("progress")
    return None, None


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "account_f"
    idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    prompt = sys.argv[3] if len(sys.argv) > 3 else None
    max_wait = int(sys.argv[4]) if len(sys.argv) > 4 else 240

    before, bp = progress(key)
    print("[before] %s Expert_team_use_3 = %s %s" % (key, before, bp), flush=True)

    titles_before = U.stable_task_titles()
    print("[titles_before] %s" % json.dumps(titles_before, ensure_ascii=False)[:200], flush=True)

    sw = AS.switch_to(key, reload=False, verify=True)
    print("[switch] ok=%s menu=%s" % (sw.get("ok"), (sw.get("after") or {}).get("menu")), flush=True)
    if not sw.get("ok"):
        print("switch failed -> abort")
        return 1

    steps, gaps = UT._expert_steps("team", None, idx)
    p = prompt or "用一句话简单介绍你自己。直接回答，不要反问。"
    print("[prompt] %s" % p, flush=True)

    t0 = time.time()
    r = U.run_task(template=None, prompt=p, model=None, use_template=False,
                   pre_steps=steps, pre_gap=gaps, keep_input=True, pre_clear=True,
                   pre_must_ok=True, delete_after=False, max_wait=max_wait)
    dt = time.time() - t0

    pre = r.get("pre") or {}
    run = r.get("run") or {}
    lg = run.get("log") or []
    nags = [x.get("nAg") for x in lg if isinstance(x, dict)]
    print("[result] secs=%.0f ok=%s sent=%s err=%s" % (dt, r.get("ok"), r.get("sent"), r.get("err")), flush=True)
    print("[pre] team=%s summoned=%s confirmed=%s" % (pre.get("name"), pre.get("ok"), pre.get("confirmed")), flush=True)
    print("[steps] " + json.dumps(
        [{"ok": (s or {}).get("ok"), "err": (s or {}).get("err"),
          "confirmed": (s or {}).get("confirmed"), "dialog": (s or {}).get("dialog")}
         for s in (r.get("pre_steps") or [])], ensure_ascii=False), flush=True)
    print("[run] done=%s reason=%s quota=%s" % (run.get("done"), run.get("reason"), run.get("quota")), flush=True)
    print("[agents] max_nAg=%s  trace=%s" % (max(nags) if nags else None, nags[:20]), flush=True)
    print("[final] %s" % json.dumps(run.get("final"), ensure_ascii=False), flush=True)

    time.sleep(3)
    after, ap = progress(key)
    titles_after = U.stable_task_titles()
    new = [t for t in (titles_after or []) if t not in set(titles_before or [])]
    print("[after]  %s Expert_team_use_3 = %s %s" % (key, after, ap), flush=True)
    print("[delta]  %s -> %s" % (before, after), flush=True)
    print("[new_convo] %s" % json.dumps(new, ensure_ascii=False)[:300], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
