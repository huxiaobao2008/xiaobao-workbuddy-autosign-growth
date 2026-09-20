(async () => {
  const out = { steps: [] };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60);

  await closeOverlays(3);
  await openNewTask();
  await sleep(1500);

  // 侧边栏全部入口
  out.sidebar = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
    .map(b => T(b)).filter(Boolean);

  const entry = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
    .find(b => T(b).indexOf('专家') !== -1);
  out.entry = entry ? T(entry) : null;
  if (!entry) return out;
  realClick(entry);
  await sleep(1500);

  // 轮询等卡片
  for (let i = 0; i < 20; i++) {
    if (document.querySelector('.ec-expert-card')) break;
    await sleep(900);
  }
  out.pageCls = Array.from(new Set(Array.from(document.querySelectorAll('[class*=ec-], [class*=expert]'))
    .map(e => e.className.toString().split(' ')[0]))).slice(0, 60);

  // 顶部 tab / 分类
  out.tabs = Array.from(document.querySelectorAll('button, [role=tab], [class*=tab], [class*=segment], [class*=filter]'))
    .filter(isVisible).map(e => ({ t: T(e), cls: e.className.toString().slice(0, 70) }))
    .filter(x => x.t && x.t.length <= 18).slice(0, 40);

  // 专家卡片
  const cards = Array.from(document.querySelectorAll('.ec-expert-card')).filter(isVisible);
  out.nCards = cards.length;
  out.cards = cards.slice(0, 40).map(c => {
    const btn = c.querySelector('.ec-card-summon-btn');
    return { t: T(c).slice(0, 34), hasSummon: !!btn,
             summonTxt: btn ? T(btn) : null };
  });

  // 找「腾讯轻量云」专家
  out.lighthouse = cards.map(c => T(c)).filter(t => /轻量云|腾讯云|云/.test(t)).slice(0, 10);

  return out;
})()
