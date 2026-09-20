(async () => {
  const out = {};
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 70);

  await closeOverlays(3);
  await openNewTask();
  await sleep(1400);

  // 进「专家·技能·连接器」
  for (let a = 0; a < 3; a++) {
    if (document.querySelector('.um-tab')) break;
    const e = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
      .find(b => T(b).indexOf('专家') !== -1);
    if (!e) return { err: '找不到专家·技能·连接器入口' };
    realClick(e);
    await sleep(1700);
    for (let i = 0; i < 18; i++) { if (document.querySelector('.um-tab')) break; await sleep(700); }
  }
  out.tabs = Array.from(document.querySelectorAll('.um-tab')).map(e => ({ t: T(e), cls: e.className.toString().slice(0, 50) }));

  // 点「技能」板块
  const sk = Array.from(document.querySelectorAll('.um-tab')).find(e => T(e) === '技能');
  out.skillTabFound = !!sk;
  if (sk) { realClick(sk); await sleep(3200); }

  out.pageCls = Array.from(new Set(Array.from(document.querySelectorAll('[class*=skill], [class*=um-], [class*=market]'))
    .map(e => e.className.toString().split(' ')[0]))).slice(0, 60);

  out.buttons = Array.from(document.querySelectorAll('button')).filter(isVisible).map(T)
    .filter(t => t && t.length <= 20).slice(0, 40);

  // 技能卡片
  const cards = Array.from(document.querySelectorAll('[class*=skill-card], [class*=card]')).filter(isVisible)
    .filter(e => T(e).length > 4 && T(e).length < 120);
  out.cards = cards.slice(0, 12).map(c => ({
    cls: c.className.toString().slice(0, 60), t: T(c).slice(0, 50),
    btns: Array.from(c.querySelectorAll('button')).map(T).filter(Boolean).slice(0, 6) }));

  out.body = (document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 700);
  return out;
})()
