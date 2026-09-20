# 单进程：面板 → 专家团 tab → 用 .ec-card-main 定位卡片 → 点开「独董会」→ dump 新版详情弹窗按钮。
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

  const mains = Array.from(document.querySelectorAll('.ec-card-main'));
  const names = Array.from(document.querySelectorAll('.ec-card-role')).map(x => T(x));
  const idx = names.indexOf('独董会');
  const card = mains[idx] || null;
  if (!card) return { err: '没找到独董会卡片', nMain: mains.length, names };
  // 卡片根（向上找带 ec- 前缀且含 list/card 的容器）
  const chain = []; let el = card;
  for (let i = 0; i < 5 && el; i++) {
    chain.push({ tag: el.tagName, cls: (el.className||'').toString().slice(0,90), kids: el.children.length });
    el = el.parentElement;
  }
  const rc0 = card.getBoundingClientRect();
  card.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:rc0.x+rc0.width/2, clientY:rc0.y+rc0.height/2}));
  await sleep(3000);
  const ovs = Array.from(document.querySelectorAll('[class*="overlay"], [class*="modal"], [class*="dialog"], [role="dialog"]'))
    .filter(x => x.offsetHeight > 40 && T(x).length > 10);
  const modal = ovs.slice(0, 2).map(x => ({
    cls: (x.className||'').toString().slice(0, 100),
    text: T(x).slice(0, 240),
    buttons: Array.from(x.querySelectorAll('button')).map(b => ({ cls: (b.className||'').toString().slice(0, 80), t: T(b).slice(0, 18), track: b.getAttribute('data-track-id') || '', disabled: b.disabled }))
  }));
  document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true}));
  await sleep(700);
  return { nMain: mains.length, chain, names, modal };
})()
"""
print(json.dumps(U.js(BLOCK, timeout=240), ensure_ascii=False, indent=2)[:5000])
cdp.close()
