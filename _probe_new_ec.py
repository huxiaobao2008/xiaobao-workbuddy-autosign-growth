# 单进程一次跑完的探测：进专家中心 → 切「专家团」→ 抓新版的卡片/弹窗结构。
# 只读 + 一次切 tab 点击，不召唤、不发送、不花积分。
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
  const log = [];
  const entry = () => Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
    .find(b => T(b).indexOf('专家') !== -1);
  const ecOpen = () => !!document.querySelector('.ec-main-scroll');

  // 1) 确保专家中心打开
  if (!ecOpen()) {
    const e = entry();
    if (!e) return { err: '侧边栏找不到专家入口' };
    const rc = e.getBoundingClientRect();
    e.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:rc.x+rc.width/2, clientY:rc.y+rc.height/2}));
    for (let i = 0; i < 40; i++) { await sleep(500); if (ecOpen()) break; }
  }
  if (!ecOpen()) return { err: '专家中心没打开' };
  await sleep(2500);
  log.push('panel open');

  // 2) 切到「专家团」列表 tab
  const tabs = Array.from(document.querySelectorAll('.ec-list-tab'));
  const tabNames = tabs.map(T);
  const teamTab = tabs.find(x => T(x) === '专家团');
  if (teamTab && (teamTab.className || '').toString().indexOf('is-active') === -1) {
    const rc = teamTab.getBoundingClientRect();
    teamTab.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:rc.x+rc.width/2, clientY:rc.y+rc.height/2}));
    await sleep(3000);
  }
  await sleep(1500);

  // 3) 抓「专家团」tab 下所有 ec-* 类名
  const cls = {};
  document.querySelectorAll('*').forEach(el => {
    const c = (el.className || '').toString();
    if (typeof c !== 'string' || !c) return;
    c.split(/\s+/).forEach(x => { if (x.indexOf('ec-') === 0) cls[x] = (cls[x] || 0) + 1; });
  });
  const top = Object.entries(cls).sort((a,b) => b[1]-a[1]).slice(0, 45);

  // 4) 找卡片候选：已知团队名 → 元素链
  const KNOWN = ['独董会', '智数分析专家团', '腾讯云技术支持', '工程保障团队', '软件工坊', '内容创作专家团', '科研专家团'];
  const found = [];
  for (const name of KNOWN) {
    const leaf = Array.from(document.querySelectorAll('span,div,h3,h4,p'))
      .find(el => el.children.length === 0 && T(el) === name);
    if (!leaf) { found.push({ name, hit: false }); continue; }
    const chain = []; let el = leaf;
    for (let i = 0; i < 5 && el; i++) {
      chain.push({ tag: el.tagName, cls: (el.className || '').toString().slice(0, 80), kids: el.children.length });
      el = el.parentElement;
    }
    found.push({ name, hit: true, chain });
  }
  // 5) 分类 tab 的新类名
  const catRow = Array.from(document.querySelectorAll('[class*="categor"], [class*="filter"], [class*="chip"]'))
    .slice(0, 6).map(x => ({ cls: (x.className||'').toString().slice(0,60), n: x.children.length, t: T(x).slice(0, 60) }));
  return { tabNames, top, found, catRow, mainScroll: true };
})()
"""

print(json.dumps(U.js(BLOCK, timeout=240), ensure_ascii=False, indent=2)[:5000])
cdp.close()
