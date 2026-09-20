# 只读：逐条点开会话，读输入框上的专家团 chip → 建立「会话主题 → 团队」映射。
# 不发送、不删除；每条只读 chip 后继续下一条。
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
print("[switch]", KEY, r.get("ok"), nick)

# 逐条点开：读 chip（cr-chip-label / aria-label="清除专家: xxx"）
BLOCK = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const items = Array.from(document.querySelectorAll('.conversation-section-tasks .conversation-item'));
  const out = [];
  for (let i = 0; i < items.length; i++) {
    const it = items[i];
    const title = T(it).replace(/\s+\d+\s*(秒|分钟|小时|天)前$/, '').replace(/\s+刚刚$/, '').slice(0, 44);
    const card = it.querySelector('.cb-agent-card') || it;
    const r0 = card.getBoundingClientRect();
    card.dispatchEvent(new MouseEvent('click', {bubbles: true, clientX: r0.x + r0.width / 2, clientY: r0.y + r0.height / 2}));
    await sleep(1600);
    const chips = Array.from(document.querySelectorAll('.cr-chip-label, [aria-label^="清除专家"]'))
      .map(c => (c.getAttribute('aria-label') || T(c)).replace('清除专家: ', '').trim())
      .filter(Boolean);
    const uniq = Array.from(new Set(chips));
    out.push({ i: i + 1, title: title, chips: uniq });
  }
  return out;
})()
"""
res = U.js(BLOCK, timeout=300)
print("[map] %d 条:" % len(res or []))
for x in (res or []):
    print("  %2d. %-44s -> %s" % (x["i"], x["title"], x["chips"] or "(无 chip)"))
cdp.close()
