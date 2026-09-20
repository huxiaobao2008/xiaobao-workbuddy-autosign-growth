# -*- coding: utf-8 -*-
"""探针 v5：用**修好后的**专家团驱动跑 1 个团队，验证进度是否 +1。

用法: python _probe_v5.py <account_key> <idx>
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import auto_buddy as core      # noqa: E402
import account_switch as AS    # noqa: E402
import tasks as T              # noqa: E402
import ui_tasks as UT          # noqa: E402


def progress(key):
    cfg = core.load_config()
    acc = next((a for a in cfg["accounts"] if a["key"] == key), None)
    cred, _ = core.load_cred(acc)
    tl, _ = T.fetch_tasks(cred, cfg)
    for t in (tl or []):
        if t.get("code") == "Expert_team_use_3":
            return t.get("progress_text")
    return None


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "account_f"
    idx = int(sys.argv[2]) if len(sys.argv) > 2 else 4

    print("[before] %s team3=%s" % (key, progress(key)), flush=True)
    sw = AS.switch_to(key, reload=False, verify=True)
    print("[switch] ok=%s menu=%s" % (sw.get("ok"), (sw.get("after") or {}).get("menu")), flush=True)

    t0 = time.time()
    r = UT.run_expert_once(kind="team", idx=idx, prompt="", max_wait=420, delete_after=False)
    dt = time.time() - t0

    pre = r.get("pre") or {}
    run = r.get("run") or {}
    lg = run.get("log") or []
    nags = [x.get("nAg") for x in lg if isinstance(x, dict)]
    print("[result] secs=%.0f ok=%s sent=%s stopped=%s" % (dt, r.get("ok"), r.get("sent"), r.get("stopped")), flush=True)
    print("[pre] team=%s summoned=%s" % (pre.get("name"), pre.get("ok")), flush=True)
    print("[steps] " + json.dumps(r.get("pre_steps"), ensure_ascii=False)[:700], flush=True)
    print("[run] done=%s reason=%s" % (run.get("done"), run.get("reason")), flush=True)
    print("[agents] max=%s trace=%s" % (max(nags) if nags else None, nags[:24]), flush=True)
    print("[final] %s" % json.dumps(run.get("final"), ensure_ascii=False), flush=True)
    print("[titles] %s" % json.dumps(r.get("new_titles"), ensure_ascii=False)[:300], flush=True)

    # 跑完后看一眼这条会话到底是不是「团队会话」（团队会有成员/角色相关 DOM）
    import ui_driver as U
    dom = U.js(r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const v = document.querySelector('.cr-message-list-viewport');
  const teamish = [];
  document.querySelectorAll('[class*=team],[class*=expert],[class*=role]').forEach(el => {
    const c = (el.className || '').toString();
    if (c && teamish.length < 12) teamish.push(c.slice(0, 70));
  });
  return { agents: document.querySelectorAll('.cr-agent').length,
           vLen: v ? (v.innerText || '').length : 0,
           head: v ? T(v).slice(0, 180) : null,
           teamish: Array.from(new Set(teamish)) };
})()
""", timeout=40)
    print("[convDOM] %s" % json.dumps(dom, ensure_ascii=False)[:800], flush=True)

    time.sleep(3)
    print("[after]  %s team3=%s" % (key, progress(key)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
