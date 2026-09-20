(async () => {
  const out = {};
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 80);

  await closeOverlays(3);
  await openNewTask();
  await sleep(1200);
  const entry = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
    .find(b => T(b).indexOf('专家') !== -1);
  realClick(entry);
  await sleep(1500);
  for (let i = 0; i < 20; i++) { if (document.querySelector('.ec-list-tab')) break; await sleep(800); }

  // 搜索框
  const si = document.querySelector('.ec-search-wrapper input');
  out.searchInput = si ? { cls: si.className.toString().slice(0, 60), ph: si.getAttribute('placeholder') } : null;

  // 切到「专家团」
  const teamTab = Array.from(document.querySelectorAll('.ec-list-tab')).find(e => T(e) === '专家团');
  out.teamTabFound = !!teamTab;
  if (teamTab) {
    realClick(teamTab);
    await sleep(2500);
    out.teamPageCls = Array.from(new Set(Array.from(document.querySelectorAll('[class*=ec-]'))
      .map(e => e.className.toString().split(' ')[0]))).slice(0, 50);
    const cards = Array.from(document.querySelectorAll('.ec-expert-card, [class*=card]'))
      .filter(isVisible).filter(e => /召唤|启用|使用/.test(T(e)));
    out.teamCards = cards.slice(0, 20).map(c => {
      const btns = Array.from(c.querySelectorAll('button')).map(b => T(b)).filter(Boolean);
      return { t: T(c).slice(0, 50), btns: btns };
    });
    // 团队可能的容器
    out.teamClasses = Array.from(new Set(Array.from(document.querySelectorAll('[class*=team], [class*=scene]'))
      .map(e => e.className.toString().split(' ')[0]))).slice(0, 30);
  }

  // 回到「专家」并搜索 轻量云
  const expTab = Array.from(document.querySelectorAll('.ec-list-tab')).find(e => T(e) === '专家');
  if (expTab) { realClick(expTab); await sleep(1800); }
  if (si) {
    setReactInput(si, '轻量云');
    await sleep(3500);
    out.searchResults = Array.from(document.querySelectorAll('.ec-expert-card'))
      .map(c => T(c).slice(0, 50)).slice(0, 20);
    out.searchResultCount = document.querySelectorAll('.ec-expert-card').length;
  }
  return out;
})()
