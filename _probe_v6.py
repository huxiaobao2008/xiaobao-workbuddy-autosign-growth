# -*- coding: utf-8 -*-
"""探针 v6：验证「专家团是否需要更强的模型才肯真正协作」。

假设：团队任务被自动降到 Hy3（最省）后，多智能体协作静默退化 → 只有 1 个 agent → 不计数。
做法：用 Deepseek-V4.1-Flash（0.03x，便宜）跑 1 个团队，等它真正跑完，看 agent 数与进度。

用法: python _probe_v6.py <account_key> <idx> <model>
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
            return t.get("progress_text")
    return None


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "account_f"
    idx = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    model = sys.argv[3] if len(sys.argv) > 3 else "Deepseek-V4.1-Flash"
    # argv[4]: "del" 则跑完删掉自己建的会话（默认不删，方便看内容）
    do_del = (len(sys.argv) > 4 and sys.argv[4] == "del")

    print("[before] %s team3=%s" % (key, progress(key)), flush=True)
    sw = AS.switch_to(key, reload=False, verify=True)
    print("[switch] ok=%s menu=%s" % (sw.get("ok"), (sw.get("after") or {}).get("menu")), flush=True)

    # 客户端当前选中的模型（我们动手前）
    print("[model_now] %s" % json.dumps(U.js(r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const el = document.querySelector('[class*=model-selector],[class*=modelSelector],[class*=model-trigger]');
  return el ? T(el).slice(0, 40) : null;
})()
""", timeout=30), ensure_ascii=False), flush=True)

    t0 = time.time()
    r = UT.run_expert_once(kind="team", idx=idx, prompt="", model=model,
                           max_wait=600, delete_after=do_del)
    dt = time.time() - t0

    pre = r.get("pre") or {}
    run = r.get("run") or {}
    lg = run.get("log") or []
    nags = [x.get("nAg") for x in lg if isinstance(x, dict)]
    print("[result] secs=%.0f ok=%s sent=%s model_used=%s" % (dt, r.get("ok"), r.get("sent"), r.get("model_used")), flush=True)
    print("[pre] team=%s summoned=%s" % (pre.get("name"), pre.get("ok")), flush=True)
    print("[steps] %s" % json.dumps(r.get("pre_steps"), ensure_ascii=False)[:600], flush=True)
    print("[run] done=%s reason=%s" % (run.get("done"), run.get("reason")), flush=True)
    print("[agents] max=%s trace=%s" % (max(nags) if nags else None, nags[:30]), flush=True)
    print("[final] %s" % json.dumps(run.get("final"), ensure_ascii=False), flush=True)

    dom = U.js(r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const v = document.querySelector('.cr-message-list-viewport');
  const cls = new Set();
  document.querySelectorAll('[class*=cr-]').forEach(el => {
    const c = (el.className || '').toString().split(/\s+/)[0];
    if (c && cls.size < 30) cls.add(c);
  });
  return { agents: document.querySelectorAll('.cr-agent').length,
           vLen: v ? (v.innerText || '').length : 0,
           head: v ? T(v).slice(0, 260) : null,
           tail: v ? T(v).slice(-200) : null,
           crClasses: Array.from(cls) };
})()
""", timeout=40)
    print("[convDOM] %s" % json.dumps(dom, ensure_ascii=False)[:1100], flush=True)

    time.sleep(4)
    print("[after]  %s team3=%s" % (key, progress(key)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
