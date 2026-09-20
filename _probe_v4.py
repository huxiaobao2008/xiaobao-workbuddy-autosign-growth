# -*- coding: utf-8 -*-
"""探针 v4：走真人路径 —— 点团队**卡片**打开详情弹窗 → 点弹窗内的「立即召唤」→ 处理确认弹窗 → 发送。

对照 v3（点卡片角落的小「召唤」按钮）看是否有「积分消耗提醒」弹窗、团队是否真的协作。
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
IDX = int(sys.argv[2]) if len(sys.argv) > 2 else 3

CLICK_CARD = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  let cards = [];
  for (let i = 0; i < 30; i++) {
    cards = Array.from(document.querySelectorAll('.ec-expert-card'));
    if (cards.length) break;
    await sleep(600);
  }
  if (!cards.length) return { ok: false, err: 'no cards' };
  const idx = %d;
  const card = cards[idx] || cards[0];
  const name = T(card).slice(0, 40);
  realClick(card);            // 点整张卡片 -> 打开团队详情弹窗
  return { ok: true, name: name, n: cards.length };
})()
"""

DUMP = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const dialogs = [];
  document.querySelectorAll('*').forEach(el => {
    const c = (el.className || '').toString();
    if (/overlay|dialog|modal/i.test(c) && c.indexOf('ec-featured-scene-overlay') === -1) {
      const r = el.getBoundingClientRect();
      if (r.width > 100 && r.height > 60) {
        const t = T(el);
        if (t) dialogs.push({ cls: c.slice(0, 80), txt: t.slice(0, 260),
          btns: Array.from(el.querySelectorAll('button')).map(b => T(b).slice(0, 20)).slice(0, 8) });
      }
    }
  });
  const ed = document.querySelector('[contenteditable=true]');
  return { dialogs: dialogs.slice(0, 4), edText: ed ? T(ed).slice(0, 140) : null,
           agents: document.querySelectorAll('.cr-agent').length,
           sendCls: (() => { const b = document.querySelector('button.cr-send-button');
                             return b ? (b.className || '').toString().slice(0, 60) : null; })() };
})()
"""

CLICK_MODAL_SUMMON = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  for (let i = 0; i < 20; i++) {
    const b = document.querySelector('.ec-modal-summon-btn')
      || Array.from(document.querySelectorAll('button'))
           .find(x => /召唤专家团|立即召唤/.test(T(x)));
    if (b) { realClick(b); return { ok: true, text: T(b).slice(0, 24), cls: (b.className||'').toString().slice(0,70) }; }
    await sleep(500);
  }
  return { ok: false, err: '弹窗里找不到召唤按钮' };
})()
"""

CONFIRM = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const out = {};
  const ov = document.querySelector('.ec-team-summon-confirm-overlay');
  out.dialog = !!ov;
  if (ov) {
    const lab = ov.querySelector('label.ec-confirm-dialog-checkbox')
      || Array.from(ov.querySelectorAll('label')).find(l => /已知悉|acknowledge/i.test(T(l)));
    if (lab) { realClick(lab); out.checked = true; }
    await sleep(600);
    const go = ov.querySelector('[data-track-id=expert_team_confirm_continue]')
      || Array.from(ov.querySelectorAll('button')).find(b => /继续/.test(T(b)));
    if (go) { out.disabled = go.disabled; if (!go.disabled) { realClick(go); out.confirmed = true; } }
    else out.err = 'no continue button';
  }
  return out;
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

    U.js("(async()=>{await openNewTask(); return {ok:true};})()", timeout=60)
    print("[clear]", json.dumps(U.clear_input(), ensure_ascii=False), flush=True)
    print("[enter]", json.dumps(U.js(UT.EXPERT_ENTER_STEP, timeout=60), ensure_ascii=False), flush=True)
    print("[tab]  ", json.dumps(U.js(UT._expert_steps("team", None, 0)[0][1], timeout=60), ensure_ascii=False), flush=True)
    time.sleep(5)

    print("[card] ", json.dumps(U.js(CLICK_CARD % IDX, timeout=60), ensure_ascii=False), flush=True)
    time.sleep(3)
    print("[after card click] ", json.dumps(U.js(DUMP, timeout=40), ensure_ascii=False)[:900], flush=True)

    print("[modal summon] ", json.dumps(U.js(CLICK_MODAL_SUMMON, timeout=60), ensure_ascii=False), flush=True)
    time.sleep(3)
    print("[after modal summon] ", json.dumps(U.js(DUMP, timeout=40), ensure_ascii=False)[:900], flush=True)

    print("[confirm] ", json.dumps(U.js(CONFIRM, timeout=60), ensure_ascii=False), flush=True)
    time.sleep(3)
    print("[after confirm] ", json.dumps(U.js(DUMP, timeout=40), ensure_ascii=False)[:900], flush=True)

    print("[send] ", json.dumps(U.js("(async()=>{const s=send(); return s;})()", timeout=60), ensure_ascii=False), flush=True)
    t0 = time.time()
    maxag = 0
    while time.time() - t0 < 240:
        time.sleep(10)
        d = U.js(DUMP, timeout=40) or {}
        maxag = max(maxag, d.get("agents") or 0)
        print("   t=%3ds agents=%s send=%s" % (int(time.time() - t0), d.get("agents"),
                                               (d.get("sendCls") or "")[-22:]), flush=True)
        if time.time() - t0 > 60 and not (d.get("sendCls") or "").endswith("--stop"):
            break
    print("[max_agents] %d" % maxag, flush=True)
    time.sleep(4)
    print("[after] %s team3=%s" % (KEY, progress(KEY)), flush=True)
    print("[titles] %s" % json.dumps(U.stable_task_titles(), ensure_ascii=False)[:400], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
