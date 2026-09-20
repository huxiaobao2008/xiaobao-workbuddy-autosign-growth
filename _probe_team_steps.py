# 单团队逐步诊断（乡下人 account_e）：把 pre_steps 每一步的真实返回值全打出来，
# 找到「确认框 / 召唤 / 发送」到底卡在哪一步。
import sys, json, time
sys.path.insert(0, r"D:\workbuddy\2026-09-19-00-30-03\buddy-auto")
from cdp import connect, unhide
import ui_driver as U
import ui_tasks as UT
import account_switch as AS

KEY = "account_e"; NICK = "乡下人"; IDX = int(sys.argv[1]) if len(sys.argv) > 1 else 9

cdp, page = connect()
unhide(cdp)
print("[hidden]", U.js("document.hidden", timeout=15))
nick0 = U.js("(document.querySelector('.user-menu-trigger')||{innerText:''}).innerText.trim()", timeout=20)
print("[current]", nick0)
if not (nick0 and NICK in str(nick0)):
    r = AS.switch_to(KEY, reload=False)
    # 切号是「慢生效」的：switch_to 返回 ok=False 不代表没成，必须自己轮询核对
    ok = False
    for _ in range(20):
        time.sleep(1.5)
        nick = U.js("(document.querySelector('.user-menu-trigger')||{innerText:''}).innerText.trim()", timeout=20)
        if nick and NICK in str(nick):
            ok = True
            break
    print("[switch]", r.get("ok"), "->", nick, "ok=%s" % ok)
    if not ok:
        print("[ABORT] 账号核对失败（当前=%s 期望=%s）—— 拒绝在错误账号上执行" % (nick, NICK))
        cdp.close(); sys.exit(2)
else:
    print("[switch] 已在目标账号，跳过")

print("[0] 清 suppress:", json.dumps(U.reset_team_summon_suppress(), ensure_ascii=False))

# 逐步手工执行 team 流程（不用 run_task 的 pre_steps，便于逐步观察）
print("[1] EXPERT_ENTER:", json.dumps(U.js(UT.EXPERT_ENTER_STEP, timeout=120), ensure_ascii=False)[:150])
pick = UT._as_fn(UT.EXPERT_PICK_STEP)
print("[2] pick team:", json.dumps(U.js("(async () => { const f = %s; return await f('team', null, 0); })()" % pick, timeout=90), ensure_ascii=False)[:150])
print("[3] open modal #%d:" % IDX, json.dumps(U.js(UT.EXPERT_TEAM_OPEN_MODAL_STEP % IDX, timeout=90), ensure_ascii=False)[:200])
print("[4] summon:", json.dumps(U.js(UT.EXPERT_TEAM_MODAL_SUMMON_STEP, timeout=90), ensure_ascii=False)[:250])
print("[4.5] 确认框内容:", json.dumps(U.js(r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const ov = document.querySelector('.ec-team-summon-confirm-overlay') || document.querySelector('[class*="_dialogOverlay"]');
  if (!ov) return { found: false };
  const btn = ov.querySelector('[data-track-id=expert_team_confirm_continue]');
  return { found: true, text: T(ov).slice(0, 220),
           goBtn: btn ? { disabled: btn.disabled, cls: (btn.className||'').toString().slice(0,60) } : null };
})()
""", timeout=40), ensure_ascii=False)[:500])
print("[5] ACK（真实鼠标，Python 步骤）:")
_r = UT.ack_team_summon_confirm()
print("   ", json.dumps(_r, ensure_ascii=False)[:400])
print("[6] STATE:", json.dumps(U.js(UT.EXPERT_STATE_STEP, timeout=60), ensure_ascii=False)[:300])
print("[7] 输入框:", json.dumps(U.js(r"""
(() => {
  const ta = document.querySelector('textarea, [contenteditable="true"], .cr-input');
  return { len: ta ? (ta.value || ta.innerText || '').length : -1,
           head: ta ? (ta.value || ta.innerText || '').replace(/\s+/g,' ').slice(0, 60) : '' };
})()
""", timeout=30), ensure_ascii=False)[:250])
print("[8] 当前界面:", json.dumps(U.js(r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const chip = Array.from(document.querySelectorAll('[class*="chip"]')).map(x => T(x).slice(0, 30)).slice(0, 5);
  return { chip: chip, bodyHead: document.body.innerText.replace(/\s+/g,' ').slice(0, 150) };
})()
""", timeout=30), ensure_ascii=False)[:400])

AS.switch_to("account_a", reload=False)
print("[back] done")
cdp.close()
