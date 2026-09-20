# 单进程：面板 → 专家团 tab → 抓卡片根类名/召唤按钮 → 点开一张卡片看新版详情弹窗结构 → Esc 关闭。
# 只点开详情弹窗（不召唤、不发送）。
import sys, json
sys.path.insert(0, r"D:\workbuddy\2026-09-19-00-30-03\buddy-auto")
from cdp import connect, unhide
import ui_driver as U

cdp, page = connect()
unhide(cdp)

BLOCK = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const entry = () => Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
    .find(b => T(b).indexOf('专家') !== -1);
  const panelUp = () => !!document.querySelector('.ec-list-tab');
  for (let round = 0; round < 3; round++) {
    if (panelUp()) break;
    const e = entry(); if (!e) return { err: 'no entry' };
    const rc = e.getBoundingClientRect();
    e.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:rc.x+rc.width/2, clientY:rc.y+rc.height/2}));
    for (let i = 0; i < 24; i++) { await sleep(500); if (panelUp()) break; }
  }
  if (!panelUp()) return { err: 'panel not up' };
  await sleep(2000);
  const teamTab = Array.from(document.querySelectorAll('.ec-list-tab')).find(x => T(x) === '专家团');
  if (teamTab && (teamTab.className||'').toString().indexOf('is-active') === -1) {
    const rc = teamTab.getBoundingClientRect();
    teamTab.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:rc.x+rc.width/2, clientY:rc.y+rc.height/2}));
    await sleep(3500);
  }
  await sleep(2000);

  // 1) 卡片根：从 .ec-card-role 向上找到「唯一带 ec-card 前缀但不带后缀」的祖先
  const role = document.querySelector('.ec-card-role');
  if (!role) return { err: '没有 .ec-card-role' };
  let root = role, rootCls = '';
  for (let i = 0; i < 8 && root; i++) {
    const c = (root.className || '').toString();
    if (/(^|\s)ec-card(\s|$)/.test(c)) { rootCls = c; break; }
    root = root.parentElement;
  }
  const cards = Array.from(document.querySelectorAll('.ec-card'));
  const cardInfo = cards.slice(0, 3).map(c => ({
    cls: (c.className||'').toString().slice(0, 80),
    name: T(c.querySelector('.ec-card-role') || c).slice(0, 24),
    buttons: Array.from(c.querySelectorAll('button')).map(b => ({ cls: (b.className||'').toString().slice(0,70), t: T(b).slice(0, 16), track: b.getAttribute('data-track-id') || '' }))
  }));
  const names = Array.from(document.querySelectorAll('.ec-card-role')).map(x => T(x));

  // 2) 点开「独董会」卡片 → 看新版详情弹窗
  const idx = names.indexOf('独董会');
  let modal = null;
  if (idx >= 0 && cards[idx]) {
    const rc = cards[idx].getBoundingClientRect();
    cards[idx].dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:rc.x+rc.width/2, clientY:rc.y+rc.height/2}));
    await sleep(2500);
    const ov = Array.from(document.querySelectorAll('[class*="overlay"], [class*="modal"], [class*="dialog"]'))
      .filter(el => el.offsetHeight > 40 && T(el).length > 20);
    modal = ov.slice(0, 3).map(el => ({
      cls: (el.className||'').toString().slice(0, 90),
      text: T(el).slice(0, 200),
      buttons: Array.from(el.querySelectorAll('button')).map(b => ({ cls: (b.className||'').toString().slice(0,80), t: T(b).slice(0, 18), track: b.getAttribute('data-track-id') || '' }))
    }));
    // 关掉
    document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true}));
    await sleep(800);
  }
  return { rootCls, nCards: cards.length, names, cardInfo, modal };
})()
"""
print(json.dumps(U.js(BLOCK, timeout=240), ensure_ascii=False, indent=2)[:5000])
cdp.close()
