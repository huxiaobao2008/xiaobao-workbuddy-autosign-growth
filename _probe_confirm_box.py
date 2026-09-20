# 只读探测：g 号上清 suppress → 独董会弹窗 → 点召唤 → dump 确认框完整 DOM。
# 不发送消息；最后用「取消/Esc」关掉确认框。
import sys, json, time
sys.path.insert(0, r"D:\workbuddy\2026-09-19-00-30-03\buddy-auto")
from cdp import connect, unhide
import ui_driver as U
import ui_tasks as UT
import account_switch as AS

KEY = "account_g"
NICK = "15047889319"
IDX = 6

cdp, page = connect()
unhide(cdp)
r = AS.switch_to(KEY, reload=False)
time.sleep(2)
nick = U.js("(document.querySelector('.user-menu-trigger')||{innerText:''}).innerText.trim()", timeout=20)
print("[switch]", r.get("ok"), nick)
if not (nick and NICK in str(nick)):
    print("[ABORT] 账号核对失败")
    cdp.close(); sys.exit(2)

print("[reset]", json.dumps(U.reset_team_summon_suppress(), ensure_ascii=False))

print("[enter]", json.dumps(U.js(UT.EXPERT_ENTER_STEP, timeout=120), ensure_ascii=False)[:120])
pick = UT._as_fn(UT.EXPERT_PICK_STEP)
print("[pick]", json.dumps(U.js("(async () => { const f = %s; return await f('team', null, 0); })()" % pick, timeout=90), ensure_ascii=False)[:120])
print("[modal]", json.dumps(U.js(UT.EXPERT_TEAM_OPEN_MODAL_STEP % IDX, timeout=90), ensure_ascii=False)[:150])
print("[summon]", json.dumps(U.js(UT.EXPERT_TEAM_MODAL_SUMMON_STEP, timeout=90), ensure_ascii=False)[:200])

DUMP = r"""
(() => {
  const ACK = '我已知悉', T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  // 找包含确认文案的最小容器
  const hits = Array.from(document.querySelectorAll('div, section'))
    .filter(el => (el.innerText || '').indexOf(ACK) !== -1)
    .sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
  const dlg = hits[0];
  if (!dlg) return { found: false };
  const checkboxes = Array.from(dlg.querySelectorAll('label, [class*="checkbox"]'))
    .map(l => ({ cls: (l.className || '').toString().slice(0, 60), text: T(l).slice(0, 40) }));
  const buttons = Array.from(dlg.querySelectorAll('button'))
    .map(b => ({ cls: (b.className || '').toString().slice(0, 60), text: T(b).slice(0, 24),
                 disabled: b.disabled,
                 track: b.getAttribute('data-track-id') || '' }));
  return { found: true, cls: (dlg.className || '').toString().slice(0, 80),
           fullText: T(dlg).slice(0, 400), checkboxes, buttons };
})()
"""
d = U.js(DUMP, timeout=40)
print("[confirm-box dump]")
print(json.dumps(d, ensure_ascii=False, indent=2)[:2600])

# 关掉确认框（Esc）
U.js("document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true})); 'esc'", timeout=20)
time.sleep(1)
back = AS.switch_to("account_a", reload=False)
print("[back]", back.get("ok"))
cdp.close()
