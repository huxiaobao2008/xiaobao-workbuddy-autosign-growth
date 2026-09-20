# -*- coding: utf-8 -*-
"""探针 v3：走「输入框留空 → 召唤团队 → 直接用团队推荐提示词发送」的正规路径。

全程手工分步，目的是看清：
  1) 召唤后是否弹「积分消耗提醒」/「promptOverwrite」；
  2) 输入框里到底是什么；
  3) 发送后团队是否进入协作（多个 agent）；
  4) 进度是否 +1。
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

KEY = sys.argv[1] if len(sys.argv) > 1 else "account_f"
IDX = int(sys.argv[2]) if len(sys.argv) > 2 else 2

DUMP = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const dialogs = [];
  document.querySelectorAll('*').forEach(el => {
    const c = (el.className || '').toString();
    if (/overlay|dialog|modal/i.test(c) && !/^ec-featured-scene-overlay$/.test(c)) {
      const r = el.getBoundingClientRect();
      if (r.width > 80 && r.height > 50) {
        const t = T(el);
        if (t) dialogs.push({ cls: c.slice(0, 90), txt: t.slice(0, 220),
          btns: Array.from(el.querySelectorAll('button')).map(b => T(b)).slice(0, 6) });
      }
    }
  });
  const ed = document.querySelector('[contenteditable=true]');
  return {
    dialogs: dialogs.slice(0, 5),
    edText: ed ? T(ed).slice(0, 160) : null,
    agents: document.querySelectorAll('.cr-agent').length,
    sendCls: (() => { const b = document.querySelector('button.cr-send-button');
                      return b ? (b.className || '').toString().slice(0, 60) : null; })()
  };
})()
"""

CLICK_ANY = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const want = ['继续使用', '继续', '确认', '使用推荐'];
  const found = [];
  document.querySelectorAll('button').forEach(b => {
    const t = T(b);
    if (want.some(w => t === w || t.indexOf(w) !== -1)) {
      const r = b.getBoundingClientRect();
      if (r.width > 10 && r.height > 10 && !b.disabled) {
        realClick(b); found.push(t);
      }
    }
  });
  return { clicked: found };
})()
"""

CHECKBOX = r"""
(() => {
  const out = [];
  document.querySelectorAll('input[type=checkbox]').forEach(c => {
    const lab = c.closest('label');
    if (lab && !c.checked) { realClick(lab); out.push(true); }
  });
  return { checked: out.length };
})()
"""


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
    print("[before] %s team3=%s" % (KEY, progress(KEY)), flush=True)
    sw = AS.switch_to(KEY, reload=False, verify=True)
    print("[switch] ok=%s menu=%s" % (sw.get("ok"), (sw.get("after") or {}).get("menu")), flush=True)

    print("[1] new task page", flush=True)
    print("   ", json.dumps(U.js("(async()=>{await openNewTask(); return {ok:true};})()", timeout=60)), flush=True)
    print("[2] clear input", flush=True)
    print("   ", json.dumps(U.clear_input(), ensure_ascii=False), flush=True)

    print("[3] enter expert center", flush=True)
    print("   ", json.dumps(U.js(UT.EXPERT_ENTER_STEP, timeout=60), ensure_ascii=False), flush=True)
    print("[4] pick 专家团 tab", flush=True)
    print("   ", json.dumps(U.js(UT._expert_steps("team", None, 0)[0][1], timeout=60), ensure_ascii=False), flush=True)
    time.sleep(5)

    print("[5] dump BEFORE summon", flush=True)
    print("   ", json.dumps(U.js(DUMP, timeout=40), ensure_ascii=False)[:700], flush=True)

    print("[6] summon idx=%d" % IDX, flush=True)
    print("   ", json.dumps(U.js(UT._expert_steps("team", None, IDX)[0][2], timeout=60), ensure_ascii=False), flush=True)

    for i in range(4):
        time.sleep(3)
        d = U.js(DUMP, timeout=40)
        print("[7.%d] after summon (+%ds) dialogs=%s edText=%s"
              % (i, 3 * (i + 1), json.dumps((d or {}).get("dialogs"), ensure_ascii=False)[:400],
                 (d or {}).get("edText")), flush=True)

    print("[8] handle checkbox + confirm if any", flush=True)
    print("   ", json.dumps(U.js(CHECKBOX, timeout=30), ensure_ascii=False), flush=True)
    time.sleep(1)
    print("   ", json.dumps(U.js(CLICK_ANY, timeout=30), ensure_ascii=False), flush=True)
    time.sleep(3)
    d = U.js(DUMP, timeout=40)
    print("[9] after confirm:", json.dumps(d, ensure_ascii=False)[:600], flush=True)

    print("[10] send", flush=True)
    print("   ", json.dumps(U.js("(async()=>{const s=send(); return s;})()", timeout=60), ensure_ascii=False), flush=True)

    t0 = time.time()
    maxag = 0
    while time.time() - t0 < 300:
        time.sleep(10)
        d = U.js(DUMP, timeout=40) or {}
        maxag = max(maxag, d.get("agents") or 0)
        print("     t=%3ds agents=%s sendCls=%s" % (int(time.time() - t0), d.get("agents"), d.get("sendCls")), flush=True)
        if d.get("sendCls") and "--stop" not in (d.get("sendCls") or "") and time.time() - t0 > 40:
            break

    print("[11] max_agents=%d" % maxag, flush=True)
    time.sleep(4)
    print("[after] %s team3=%s" % (KEY, progress(KEY)), flush=True)
    titles = U.stable_task_titles()
    print("[titles] %s" % json.dumps(titles, ensure_ascii=False)[:400], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
