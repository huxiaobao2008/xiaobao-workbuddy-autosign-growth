(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  window.__st = [];
  const st = (s) => { window.__st.push(s + '@' + Date.now() % 100000); };
  st('start');
  await openNewTask();
  st('newTask');
  for (let a = 0; a < 3; a++) {
    if (document.querySelector('.ec-list-tab')) break;
    const e = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
      .find(b => T(b).indexOf('专家') !== -1);
    if (!e) { st('noSideEntry'); return { err: 'no side entry', st: window.__st }; }
    realClick(e);
    st('clicked side ' + a);
    await sleep(1600);
    for (let i = 0; i < 20; i++) { if (document.querySelector('.ec-list-tab')) break; await sleep(700); }
  }
  st('expertPage=' + !!document.querySelector('.ec-list-tab'));
  const tabName = '专家团';
  const tab = Array.from(document.querySelectorAll('.ec-list-tab')).find(x => T(x) === tabName);
  st('tabFound=' + !!tab + ' active=' + (tab ? tab.className.toString().indexOf('is-active') !== -1 : null));
  if (tab && tab.className.toString().indexOf('is-active') === -1) {
    realClick(tab);
    st('clicked tab');
    await sleep(2600);
  }
  st('afterTab');
  let cards = [];
  for (let i = 0; i < 22; i++) {
    cards = Array.from(document.querySelectorAll('.ec-expert-card'));
    if (cards.length) break;
    await sleep(700);
  }
  st('cards=' + cards.length);
  window.__cards = cards.map(T).slice(0, 6);
  return { ok: true, st: window.__st, cards: cards.length, list: window.__cards,
           empty: !!document.querySelector('.cb-overview-empty'),
           activeTabs: Array.from(document.querySelectorAll('.ec-list-tab.is-active')).map(T) };
})
