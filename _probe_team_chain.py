# 零成本验证新链路：清残骸 → reset suppress → summon_team_by_index(idx) → 真实鼠标 ACK → 状态。不发送。
import sys, json, time
sys.path.insert(0, r"D:\workbuddy\2026-09-19-00-30-03\buddy-auto")
from cdp import connect, unhide
import ui_driver as U
import ui_tasks as UT

IDX = 9 if len(sys.argv) < 2 else int(sys.argv[1])
cdp, page = connect()
unhide(cdp)

nick = UT.current_account_name()
print("[account]", nick)
if not (nick and "乡下人" in str(nick)):
    print("[ABORT] 当前不是乡下人 → 拒绝执行")
    cdp.close(); sys.exit(2)

# 清输入框 + 清掉残留的专家 chip
print("[clear]", json.dumps(U.clear_input(), ensure_ascii=False)[:120])
U.js("""
(() => {
  const btns = Array.from(document.querySelectorAll('.cr-chip-close-btn, [aria-label^="清除专家"]'));
  btns.forEach(b => { const r = b.getBoundingClientRect();
    b.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:r.x+r.width/2, clientY:r.y+r.height/2})); });
  return btns.length;
})()
""", timeout=30)
time.sleep(1)

print("[reset]", json.dumps(U.reset_team_summon_suppress(), ensure_ascii=False)[:200])
t0 = time.time()
r = UT.summon_team_by_index(IDX)
print("[summon] %.0fs" % (time.time() - t0), json.dumps(r, ensure_ascii=False)[:600])
print("[ack]", json.dumps(UT.ack_team_summon_confirm(), ensure_ascii=False)[:400])
print("[state]", json.dumps(U.js("(() => ({ panel: !!document.querySelector('.ec-list-tab'), cards: document.querySelectorAll('.ec-expert-card').length, modal: !!document.querySelector('.ec-modal-summon-btn') }))()", timeout=20), ensure_ascii=False))
print("[composer]", json.dumps(U.js(r"""
(() => {
  const ta = document.querySelector('textarea, [contenteditable="true"], .cr-input');
  const chips = Array.from(document.querySelectorAll('.cr-chip-label')).map(x => (x.innerText||'').trim());
  return { text: ta ? (ta.value || ta.innerText || '').replace(/\s+/g,' ').slice(0, 60) : '',
           chips: chips };
})()
""", timeout=30), ensure_ascii=False)[:400])
print("[done] 未发送消息")
cdp.close()
