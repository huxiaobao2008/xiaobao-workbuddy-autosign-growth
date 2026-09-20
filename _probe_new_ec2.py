# 单进程：确保专家中心打开 → 切「专家团」→ 用只出现在网格里的团队名定位，抓其类名链。
# 只读 + 切 tab 点击；不召唤、不发送。
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

  // 1) 确保面板打开（最多 3 轮）
  for (let round = 0; round < 3; round++) {
    if (panelUp()) break;
    const e = entry();
    if (!e) return { err: '找不到侧栏专家入口' };
    const rc = e.getBoundingClientRect();
    e.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:rc.x+rc.width/2, clientY:rc.y+rc.height/2}));
    for (let i = 0; i < 24; i++) { await sleep(500); if (panelUp()) break; }
  }
  if (!panelUp()) return { err: '专家中心打不开', bodyHead: document.body.innerText.replace(/\s+/g,' ').slice(0,150) };
  await sleep(2000);

  // 2) 切「专家团」tab
  let tabs = Array.from(document.querySelectorAll('.ec-list-tab'));
  const teamTab = tabs.find(x => T(x) === '专家团');
  if (teamTab && (teamTab.className || '').toString().indexOf('is-active') === -1) {
    const rc = teamTab.getBoundingClientRect();
    teamTab.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:rc.x+rc.width/2, clientY:rc.y+rc.height/2}));
    await sleep(3500);
  }
  await sleep(2000);

  // 3) 用只出现在**网格**里的团队名定位（精选场景里没有的名字）
  const GRID_ONLY = ['独董会', '智数分析专家团', '工程保障团队', '腾讯云技术支持', '内容创作专家团'];
  const out = { tabsNow: Array.from(document.querySelectorAll('.ec-list-tab')).map(x => ({t: T(x), active: (x.className||'').toString().indexOf('is-active') !== -1})), found: [] };
  for (const name of GRID_ONLY) {
    const leaf = Array.from(document.querySelectorAll('*'))
      .find(el => el.children.length === 0 && T(el) === name);
    if (!leaf) { out.found.push({ name, hit: false }); continue; }
    const chain = []; let el = leaf;
    for (let i = 0; i < 6 && el; i++) {
      chain.push({ tag: el.tagName, cls: (el.className || '').toString().slice(0, 90), kids: el.children.length });
      el = el.parentElement;
    }
    out.found.push({ name, hit: true, chain });
  }
  // 4) 类名统计（全部，不限 ec-）
  const cls = {};
  document.querySelectorAll('*').forEach(el => {
    const c = (el.className || '').toString();
    if (typeof c !== 'string' || !c) return;
    c.split(/\s+/).forEach(x => { if (/^(ec|expert|team|card)/i.test(x)) cls[x] = (cls[x]||0)+1; });
  });
  out.cls = Object.entries(cls).sort((a,b)=>b[1]-a[1]).slice(0, 35);
  return out;
})()
"""
print(json.dumps(U.js(BLOCK, timeout=240), ensure_ascii=False, indent=2)[:5000])
cdp.close()
