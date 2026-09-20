# 只读探测：进专家中心 → 切「专家团」tab → 列出真实卡片名 + 分类 tab。
# 不发送消息、不花费积分，只读取 DOM。
import sys, json
sys.path.insert(0, r"D:\workbuddy\2026-09-19-00-30-03\buddy-auto")
from cdp import connect, unhide
import ui_driver as U

cdp, page = connect()
unhide(cdp)
print("[ok] connected, page=", (page.get("url") or "")[:55])

BLOCK = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const realClick = el => { if (!el) return; const r = el.getBoundingClientRect();
    el.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:r.x+r.width/2, clientY:r.y+r.height/2})); };
  if (!document.querySelector('.ec-list-tab')) {
    const e = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
      .find(b => T(b).indexOf('专家') !== -1);
    if (!e) return { ok:false, err:'侧边栏找不到专家入口' };
    realClick(e);
    for (let i=0;i<40;i++){ if(document.querySelector('.ec-list-tab')) break; await sleep(500); }
  }
  if (!document.querySelector('.ec-list-tab')) return { ok:false, err:'专家中心未挂载' };
  // 切到「专家团」tab
  const tab = Array.from(document.querySelectorAll('.ec-list-tab')).find(x => T(x)==='专家团');
  if (tab && tab.className.toString().indexOf('is-active')===-1) { realClick(tab); }
  for (let i=0;i<30;i++){ await sleep(500);
    const cards = document.querySelectorAll('.ec-expert-card'); if (cards.length) break; }
  const cats = Array.from(document.querySelectorAll('.ec-category-tab')).map(T);
  const cards = Array.from(document.querySelectorAll('.ec-expert-card'))
    .map(c => T(c).replace(/^召唤\s*/,'').replace(/\s+/g,' ').trim().slice(0,50));
  return { ok:true, hidden:document.hidden, cats, nCards:cards.length, cards };
})()
"""
res = U.js(BLOCK, timeout=120)
print(json.dumps(res, ensure_ascii=False, indent=2)[:3000])
cdp.close()
