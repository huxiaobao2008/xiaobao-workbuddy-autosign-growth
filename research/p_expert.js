(async () => {
  const out = {};
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 44);

  await closeOverlays();
  await openNewTask();
  await sleep(1200);
  const before = taskTitles();

  // 打开专家中心
  const entry = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
    .find(b => T(b).indexOf('专家') !== -1);
  out.entry = entry ? T(entry) : null;
  if (!entry) return out;
  realClick(entry);
  await sleep(3000);

  out.tabs = Array.from(document.querySelectorAll('[class*=ec-], [class*=tab], [class*=filter]'))
    .filter(vis).map(e => T(e)).filter(t => t && t.length <= 16).slice(0, 40);
  out.cardsCls = Array.from(new Set(Array.from(document.querySelectorAll('[class*=ec-]'))
    .map(e => e.className.toString().slice(0, 80)))).slice(0, 50);

  // 专家卡片
  const cards = Array.from(document.querySelectorAll('[class*=ec-expert], [class*=expert-card], [class*=ec-card]'))
    .filter(vis);
  out.nCards = cards.length;
  out.cards = cards.slice(0, 12).map(c => ({ t: T(c), cls: c.className.toString().slice(0, 60), tag: c.tagName.toLowerCase() }));

  // 点第一个专家卡片
  if (cards.length) {
    out.clickedCard = T(cards[0]);
    realClick(cards[0]);
    await sleep(4000);
    out.afterClick = {
      href: location.href.slice(0, 80),
      hasComposer: !!document.querySelector('[contenteditable=true]'),
      hasView: !!document.querySelector('.cr-message-list-viewport'),
      newTitles: taskTitles().filter(t => before.indexOf(t) === -1),
      visible: Array.from(document.querySelectorAll('button, [class*=tab]')).filter(vis).map(e => T(e))
                 .filter(t => t && t.length <= 20).slice(0, 30),
      bodyText: (document.querySelector('.ec-expert-detail, [class*=expert-detail]') || {}).innerText
                ? document.querySelector('.ec-expert-detail, [class*=expert-detail]').innerText.replace(/\s+/g, ' ').slice(0, 300) : null
    };
  }
  return out;
})()
