# 监测：召唤后确认框是否一直存在（每 400ms 记录一次，共 12s）。
import sys, json, time
sys.path.insert(0, r"D:\workbuddy\2026-09-19-00-30-03\buddy-auto")
from cdp import connect, unhide
import ui_driver as U
import ui_tasks as UT
import account_switch as AS

IDX = int(sys.argv[1]) if len(sys.argv) > 1 else 9
cdp, page = connect()
unhide(cdp)
nick = U.js("(document.querySelector('.user-menu-trigger')||{innerText:''}).innerText.trim()", timeout=20)
print("[nick]", nick)
if "乡下人" not in str(nick):
    r = AS.switch_to("account_e", reload=False); time.sleep(2)
    print("[switch]", r.get("ok"))

print("[0] reset:", json.dumps(U.reset_team_summon_suppress(), ensure_ascii=False))
print("[1]", json.dumps(U.js(UT.EXPERT_ENTER_STEP, timeout=120), ensure_ascii=False)[:80])
pick = UT._as_fn(UT.EXPERT_PICK_STEP)
print("[2]", json.dumps(U.js("(async () => { const f = %s; return await f('team', null, 0); })()" % pick, timeout=90), ensure_ascii=False)[:80])
print("[3]", json.dumps(U.js(UT.EXPERT_TEAM_OPEN_MODAL_STEP % IDX, timeout=90), ensure_ascii=False)[:120])
print("[4]", json.dumps(U.js(UT.EXPERT_TEAM_MODAL_SUMMON_STEP, timeout=90), ensure_ascii=False)[:160])

MON = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const trace = [];
  for (let i = 0; i < 30; i++) {
    const ACK = '我已知悉并确认';
    const hasAck = Array.from(document.querySelectorAll('*')).some(el => (el.innerText || '').indexOf(ACK) !== -1);
    const ov = document.querySelector('.ec-team-summon-confirm-overlay') || document.querySelector('[class*="_dialogOverlay"]');
    const btn = document.querySelector('[data-track-id=expert_team_confirm_continue]');
    trace.push({ t: (i * 0.4).toFixed(1), ack: hasAck, ov: !!ov, btn: btn ? (btn.disabled ? 'disabled' : 'ENABLED') : null,
                 composer: !!document.querySelector('.cr-input, textarea') });
    await sleep(400);
  }
  return trace;
})()
"""
tr = U.js(MON, timeout=120)
print("[monitor] 每 0.4s 一次，共 12s：")
for x in tr:
    print("   t=%ss ack=%s overlay=%s goBtn=%s composer=%s" % (x["t"], x["ack"], x["ov"], x["btn"], x["composer"]))
cdp.close()
