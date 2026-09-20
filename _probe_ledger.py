# 只读：读指定账号的会话账本（任务区全部标题），用于核对「已用过哪些专家团」。
# 不跑任务、不删会话。
import sys, json, time
sys.path.insert(0, r"D:\workbuddy\2026-09-19-00-30-03\buddy-auto")
from cdp import connect, unhide
import ui_driver as U
import account_switch as AS

KEY = sys.argv[1] if len(sys.argv) > 1 else "account_e"

cdp, page = connect()
unhide(cdp)
r = AS.switch_to(KEY, reload=False)
time.sleep(2)
nick = U.js("(document.querySelector('.user-menu-trigger')||{innerText:''}).innerText.trim()", timeout=20)
print("[switch]", KEY, r.get("ok"), "nick=", nick)

# 任务区全部标题（不限前 8 条）
led = U.js(r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const items = Array.from(document.querySelectorAll('.conversation-section-tasks .conversation-item'));
  return items.map(it => T(it).replace(/\s+\d+\s*(秒|分钟|小时|天)前$/, '')
                              .replace(/\s+刚刚$/, '').slice(0, 76));
})()
""", timeout=40)
print("[ledger] %d 条:" % len(led or []))
for i, t in enumerate(led or []):
    print("  %2d. %s" % (i + 1, t))

# 也读一下「项目」区有没有会话（排除干扰）
other = U.js(r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  return Array.from(document.querySelectorAll('.conversation-section')).map(s => ({
    cls: (s.className || '').toString().slice(0, 50),
    n: s.querySelectorAll('.conversation-item').length
  }));
})()
""", timeout=30)
print("[sections]", json.dumps(other, ensure_ascii=False))

cdp.close()
